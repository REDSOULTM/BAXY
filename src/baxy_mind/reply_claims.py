"""Claims a reply makes that no operation backs: effects, the person's records, machine states, plans,
abilities and promises, and what a go-ahead, a call-off or an undo left undone.
"""

from __future__ import annotations

import re
from functools import lru_cache

from . import operation_floor
from .semantic.normalize import _accent_folded_with_punctuation, _policy_guard_text, alternation, fold
from .semantic import dialogue as dialogue_slot
from .semantic.web import talks_of_films
from .semantic.request import fold as _reading_fold
from .semantic.conversation import (
    asks_a_polar_question_about_the_person, asks_about_own_past_act, asks_what_this_is, asks_whether_able,
    request_names_the_act,
)
from .semantic.notes import _PERSONAL_RECORD_STORE, names_an_own_record_store
from .semantic.patterns import conversation_only_content_request
from .request_intents import _looks_like_capability_question
from .clock_facts import _calendar_contradiction, _local_now
from .failure_wording import talk_reply_tells_a_failure
from .limit_voice import _unsupported_answer_has_inability


_OBSERVED_MACHINE_CLAIM = re.compile(
    r"\b(?:"
    # Second person, present state of the person's own machine.
    r"(?:you|your)\s+(?:are|is|have|has)\s+(?:currently\s+)?"
    r"(?:sitting|looking|running|using|on|at|in)|"
    r"est[aá]s?\s+(?:actualmente\s+)?(?:en|sobre|usando|viendo|mirando)|"
    r"(?P<owned_device>tu\s+(?:pantalla|escritorio|volumen|sistema|equipo|maquina)\s+"
    r"(?:est[aá]|tiene|muestra)|"
    r"your\s+(?:screen|desktop|volume|system|machine|computer)\s+(?:is|has|shows))|"
    # Declarative report of a live device state.
    r"(?:the|el|la)\s+(?:volumen|volume|pantalla|screen|escritorio|desktop|"
    r"sonido|sound|audio)\s+(?:is|esta|está|se)\s+"
    r")",
    re.IGNORECASE,
)
_OBSERVED_MACHINE_DETAIL = re.compile(
    r"\b(?:windows\s*\d+|taskbar|barra\s+de\s+tareas|"
    r"altavoces|speakers|auriculares|headphones|"
    r"fondo|background|wallpaper|"
    r"gris|gray|grey|azul|blue|verde|green|negro|black|blanco|white|"
    r"por\s+ciento|percent|%|"
    r"bottom|top|izquierda|derecha|left|right)\b",
    re.IGNORECASE,
)
# An instrument reading BAXY could only hold by having looked: a clock time, a
# proportion, a capacity, a clock rate. This is a *closed grammatical class* --
# digits in a known shape -- rather than one more open list of nouns, which is
# the difference between a rule and the treadmill the register keeps finding.
#
# It stands on its own rather than inside the conjunction above, because the
# reading is already the whole offence: no true sentence about general
# knowledge quotes this machine's current clock.
# The trailing word boundary belongs only to the alphabetic units: "47%" is
# followed by a space, and two non-word characters in a row have no boundary
# between them, so anchoring the whole alternation would silently drop percent.
_OBSERVED_INSTRUMENT_READING = re.compile(
    r"\b\d{1,2}\s*[:.]\s*\d{2}\b"
    r"|\b\d+(?:[.,]\d+)?\s*(?:%|(?:por\s+ciento|percent|"
    r"gb|mb|kb|tb|ghz|mhz)\b)",
    re.IGNORECASE,
)
# A reading is only an offence when it is predicated of *this* machine *now*.
# V7 proved the difference is not decorative: with the reading alone as the
# trigger, four of eight ordinary sentences fired -- "la jornada laboral en
# España suele empezar a las 9:00", "el tren de las 7:45 suele ir lleno", "una
# batería de móvil pierde un 20% de capacidad en dos años". None of them says
# anything about this computer, and none of them was in the 163 consumed
# replies the first pricing used, which is exactly why that pricing read zero.
#
# What separates them is deixis, not vocabulary about machines: the offending
# sentences name *the* current value or bind it to the person's own device.
_READING_IS_ABOUT_THIS_MACHINE_NOW = re.compile(
    r"\b(?:la\s+hora\s+(?:actual|local)?\s+es|el\s+reloj\s+local\s+es|"
    r"son\s+las\b|the\s+(?:current\s+|local\s+)?(?:time|clock)\s+"
    r"(?:is|shows)|local\s+clock\s+shows|it\s+is\s+now\b)"
    r"|\b(?:tu|su|your|mi|my)\s+[\w\s]{0,24}?"
    r"(?:esta|está|es|is|has|tiene|queda|remains)\b"
    r"|\b(?:ahora\s+mismo|en\s+este\s+momento|actualmente|"
    r"right\s+now|at\s+the\s+moment|currently)\b"
    r"|\b(?:el|la)\s+(?:disco|memoria|bateria|pantalla|volumen|sistema|equipo)\s+"
    r"(?:tiene|esta|está|queda)\b"
    r"|\bthe\s+(?:disk|drive|memory|battery|screen|volume|system)\s+(?:has|is)\b",
    re.IGNORECASE,
)
# Habitual and generic framing is the opposite of a live reading, and it is what
# ordinary knowledge uses. Stated explicitly so a deictic word elsewhere in a
# clearly generic sentence cannot drag it in.
_HABITUAL_OR_GENERIC = re.compile(
    r"\b(?:suele[ns]?|solia|normalmente|habitualmente|por\s+lo\s+general|"
    r"generalmente|usually|typically|normally|generally|on\s+average|"
    r"en\s+promedio|equivale|equivalen|equals?)\b",
    re.IGNORECASE,
)


# The fabrications that carry no reading at all needed a different separator,
# and the eleven legitimate replies that killed the first attempt showed what it
# is. They were not claims about this machine: they were **questions** and
# **explicit inabilities**, which Spanish happens to build with "estás ...ndo".
# So the separator is not the claim's shape, it is whether the turn asserts at
# all. Measured over the 189 spoken replies of six consumed seals: 3 firings,
# all three genuine fabrications, and no legitimate reply.
# A possessive plus an arbitrary noun is not a machine predicate: it also
# rejected "Your name is Jordan" in373. Concrete owned-device subjects remain
# identified by the existing observation pattern, without a second noun list.
_PRESENT_STATE_CLAIM = re.compile(
    r"\b(?:la\s+hora\s+(?:actual\s+)?es|the\s+(?:current\s+)?time\s+is|"
    r"son\s+las\s+\d|it\s+is\s+\d{1,2}\s*[:.]\d{2})"
    r"|\b(?:estas|you\s+are)\s+(?:actualmente\s+|currently\s+)?\w+ndo\b"
    r"|\b(?:you\s+are|estas)\s+(?:currently\s+|actualmente\s+)?"
    r"(?:viewing|using|running|looking|viendo|usando|mirando)\b",
    re.IGNORECASE,
)
# BAXY has no eyes. A first-person claim of perception is false unless an
# operation that looks actually ran, and this guard only ever sees turns that
# executed nothing. This is not another list of machine nouns: it is the closed
# set of ways to say "I am perceiving". One firing over the same 189 replies,
# on the turn that invented a user name, and no legitimate reply.
_FIRST_PERSON_PERCEPTION = re.compile(
    r"\b(?:estoy\s+(?:mirando|viendo|observando|leyendo)"
    r"|veo\s+(?:que|la|el|un|una)"
    r"|puedo\s+ver\s+(?:que|la|el|un|una)"
    r"|i\s+(?:am|'m)\s+(?:looking\s+at|seeing|viewing|reading)"
    r"|i\s+(?:can\s+)?see\s+(?:that|the|a|an))\b",
    re.IGNORECASE,
)


# A conversation turn runs no operation, so whatever its reply says BAXY did, is doing or will do to the
# person's world, and whatever it says that world holds, is invented. The acts are written once as verbs;
# every form a reply can claim one in is generated from these tables, never listed per tense.
#
# Uso real 2026-09-25 (tanda 8): «Agregado: tomates.» was published with nothing added. Each tense had
# its own hand-written verb list (first-person preterites here, impersonal preterites and participle stems
# below, «se añadió» for four list verbs in the promises, English past forms in three more places) and the
# bare participle of a status label was the one form none of them carried.
#
# The promised forms (present with a clitic, future, «voy a …», «estoy …ndo») come from the first table
# only: «te escribo un poema», «voy a cambiar de tema», «te creo» are how a conversation speaks.
_EFFECT_INFINITIVES = (
    "guardar", "añadir", "agregar", "anotar", "apuntar", "abrir", "cerrar", "poner", "traer", "llevar",
    "enviar", "mandar", "borrar", "eliminar", "instalar", "descargar", "reproducir", "activar",
    "desactivar", "silenciar", "subir", "bajar", "programar", "apagar", "encender", "prender", "preparar",
    "cocinar", "comprar", "agendar", "recordar", "buscar", "pedir", "hacer", "arreglar", "corregir",
)
_DONE_ONLY_INFINITIVES = (
    "cliquear", "pulsar", "apretar", "mutear", "desmutear", "pausar", "detener", "parar", "desinstalar",
    "minimizar", "maximizar", "escribir", "pegar", "copiar", "reiniciar", "conectar", "desconectar", "entrar",
    "ejecutar", "cambiar", "configurar", "ajustar", "crear", "quitar", "cancelar", "vaciar",
)
# M139 (DEV-G v4n G-s120 «get a large pepperoni pie delivered from the Domino's on 5th for me» → recovered «I will get
# a large pepperoni pie delivered from Domino's on 5th for you.», published with nothing run): the acts done in the world
# by asking someone — calling, booking, paying, having something delivered — are promised or told done by BAXY in
# the first person as much as saving or opening. Only their first-person forms (the promise and «I …ed», «llamé») are
# read: their participles name things too («un amigo llamado Juan», «a friend called John»).
_WORLD_ACT_INFINITIVES = (
    "llamar", "reservar", "pagar", "encargar", "entregar", "contratar", "conseguir", "transferir",
)
_EN_WORLD_ACTS = (
    # (base, gerund, past); «get» has no past here: «I got it» is understanding.
    ("get", "getting", ""), ("deliver", "delivering", "delivered"), ("call", "calling", "called"),
    ("phone", "phoning", "phoned"), ("text", "texting", "texted"), ("email", "emailing", "emailed"),
    ("message", "messaging", "messaged"), ("reserve", "reserving", "reserved"), ("pay", "paying", "paid"),
    ("ship", "shipping", "shipped"), ("purchase", "purchasing", "purchased"), ("pick\\s+up", "picking\\s+up", "picked\\s+up"),
    ("grab", "grabbing", "grabbed"), ("contact", "contacting", "contacted"), ("hire", "hiring", "hired"),
    ("rent", "renting", "rented"), ("transfer", "transferring", "transferred"), ("cancel", "cancelling", "cancelled"),
    ("sign\\s+you\\s+up", "signing\\s+you\\s+up", "signed\\s+you\\s+up"), ("subscribe", "subscribing", "subscribed"),
    ("submit", "submitting", "submitted"), ("post", "posting", "posted"),
)
_EN_WORLD_ACT_BASE = "|".join(base for base, _, _ in _EN_WORLD_ACTS)
_EN_WORLD_ACT_GERUND = "|".join(gerund for _, gerund, _ in _EN_WORLD_ACTS)
_EN_WORLD_ACT_PAST = "|".join(past for _, _, past in _EN_WORLD_ACTS if past)
# (first person preterite, third person preterite, participle) of the irregular ones.
_IRREGULAR_DONE_FORMS = {
    "abrir": ("abrí", "abrió", "abierto"),
    "poner": ("puse", "puso", "puesto"),
    "hacer": ("hice", "hizo", "hecho"),
    "traer": ("traje", "trajo", "traído"),
    "escribir": ("escribí", "escribió", "escrito"),
    "reproducir": ("reproduje", "reprodujo", "reproducido"),
    "detener": ("detuve", "detuvo", "detenido"),
    "pedir": ("pedí", "pidió", "pedido"),
    "corregir": ("corregí", "corrigió", "corregido"),
}


def _done_forms(infinitive: str) -> tuple[str, str, str]:
    """(first person preterite, third person preterite, participle) of an effect verb."""

    if infinitive in _IRREGULAR_DONE_FORMS:
        return _IRREGULAR_DONE_FORMS[infinitive]
    stem, conjugation = infinitive[:-2], infinitive[-2:]
    if conjugation != "ar":
        return stem + "í", stem + "ió", stem + "ido"
    # The spelling keeps the sound before «é»: busqué, agregué, minimicé.
    first = stem[:-1] + "qu" if stem.endswith("c") else stem + "u" if stem.endswith("g") else (
        stem[:-1] + "c" if stem.endswith("z") else stem
    )
    return first + "é", stem + "ó", stem + "ado"


_DONE_FORMS = tuple(_done_forms(infinitive) for infinitive in _EFFECT_INFINITIVES + _DONE_ONLY_INFINITIVES)
# The same acts in English; each past is also the participle. «set» and «put» are their own present too.
_EN_DONE = (
    "added", "saved", "opened", "closed", "put", "brought", "sent", "deleted", "removed", "installed", "uninstalled",
    "downloaded", "played", "paused", "stopped", "muted", "unmuted", "set", "scheduled", "reminded", "ordered",
    "bought", "cooked", "launched", "recorded", "stored", "created", "booked", "clicked", "pressed", "raised",
    "lowered", "minimized", "minimised", "maximized", "maximised", "changed", "canceled", "cancelled", "noted",
    "searched", "fetched", "cleared", "emptied", "turned on", "turned off",
)
_EN_DONE_FORM = (
    r"(?:" + alternation(frozenset(_EN_DONE) - {"set", "put"})
    + r"|(?:set|put)(?=\s+(?:it|them|that|this|the|a|an|your|up|for|to)\b)|turned\s+it\s+(?:on|off))"
)
# Accent-folded participles in any gender and number: agregado, añadidas, puesto, hecho.
_ES_PARTICIPLE = r"(?:" + alternation(frozenset(fold(forms[2])[:-1] for forms in _DONE_FORMS)) + r")(?:o|a|os|as)"
_PC_OBJECT = (
    r"(?:volumen|volume|micr[oó]fono|microphone|mic|ventana|window|pesta[ñn]a|tab|app|aplicaci[oó]n|"
    r"application|programa|program|archivo|file|carpeta|folder|reproductor|player|canci[oó]n|song|"
    r"m[uú]sica|music|v[ií]deo|video|wifi|bluetooth|brillo|brightness|pantalla|screen|edge|chrome|"
    r"steam|spotify|discord|youtube|whatsapp|notepad|bloc de notas|calculadora|calculator|"
    r"pc|computadora|computador|ordenador|equipo|computer|sonido|sound|nota|note|alarma|alarm|"
    r"recordatorio|reminder|mensaje|message|correo|email)"
)
# The person's world: a thing on this PC or one of the person's records.
_PERSON_WORLD = re.compile(r"(?<![\w])(?:" + _PC_OBJECT + r"|" + _PERSONAL_RECORD_STORE + r")(?![\w])")
# BAXY as the one who did it, on the case-folded text with its accents («paré» is the claim, «pare» is not):
# «ya le hice click», «lo abrí», «agregué tomates», «I added it», «I set a timer».
_DONE_BY_BAXY = re.compile(
    r"(?<![\w])(?:"
    + alternation(frozenset(forms[0] for forms in _DONE_FORMS))
    # M139: «llamé», «reservé», «pagué»; «I called», «I booked … and paid».
    + r"|" + alternation(frozenset(_done_forms(infinitive)[0] for infinitive in _WORLD_ACT_INFINITIVES))
    + r"|i\s+(?:just\s+|already\s+)?(?:" + _EN_WORLD_ACT_PAST + r")"
    + r"|i\s+(?:just\s+|already\s+)?(?:" + _EN_DONE_FORM + r"|did\s+it)"
    + r"|it(?:'s|\s+is)\s+(?:done|open|closed|muted|playing)\s+now"
    + r")(?![\w])"
)
# The same on the accent-folded text: the perfect («te lo he apuntado», «I've added it») and the state it left
# («ya está hecho», «ya quedó guardado»).
_DONE_BY_BAXY_FOLDED = re.compile(
    r"(?<![\w])(?:"
    r"(?:(?:me|te|se|le|les|nos)\s+)?(?:(?:lo|la|los|las)\s+)?(?:he|hemos)\s+(?:ya\s+)?" + _ES_PARTICIPLE
    + r"|i(?:'ve|\s+have)\s+(?:just\s+|already\s+|now\s+)?" + _EN_DONE_FORM
    + r"|ya\s+(?:esta|estan|queda|quedan|quedo|quedaron)\s+(?:" + _ES_PARTICIPLE + r"|listos?|listas?|reproduciendo)"
    + r")(?![\w])"
)
# A status label at the head of a statement («Agregado: tomates.», «Listo.», «Done.», «Added to your list.»).
# A participle that goes on to describe something else («Añadido el azúcar, se bate…», «Opened to the public
# in 1889, …») is knowledge, not a report.
_STATUS_LABEL = re.compile(
    r"^\W*(?:ya\s+)?(?:" + _ES_PARTICIPLE + r"|listos?|listas?|done|all\s+set|" + alternation(frozenset(_EN_DONE))
    + r")(?=\s*(?:[:,.!…]|$)|\s+(?:a|al|en|para|to|on|in|into|for)\s+(?:(?:tu|tus|your|la|el|los|las|the)\s+)?"
    r"(?:[\w-]+\s+)?" + _PERSON_WORLD.pattern + r")"
)
# Nobody named as the doer: «el volumen se subió a 100», «quedó silenciado», «it has been added». Knowledge
# says these too («la fábrica se cerró en 1990»), so they claim only about the person's world, or when the
# sentence names nothing else and so points at what was just asked («Se añadió.», «It has been added.»).
_DONE_WITHOUT_ACTOR = re.compile(
    r"(?<![\w])(?:"
    r"se\s+(?:" + alternation(frozenset(fold(forms[1]) for forms in _DONE_FORMS)) + r"|(?:ha|han)\s+" + _ES_PARTICIPLE + r")"
    + r"|(?:quedo|quedaron|queda|quedan)\s+" + _ES_PARTICIPLE
    # Estabilización F3 (banco h1 c6 «Sí, el mensaje "prueba BAXY C6" ya fue enviado…» with nothing run): the passive
    # said as already done.
    + r"|ya\s+(?:fue|fueron|ha\s+sido|han\s+sido)\s+" + _ES_PARTICIPLE
    + r"|(?:has|have|had|is|was|got)\s+been\s+" + _EN_DONE_FORM
    + r"|(?:is|are)\s+now\s+(?:at|open|closed|muted|unmuted|playing|paused|installed|set)"
    + r")(?![\w])"
)
# «un traje», «el pedido»: after a determiner the form is a noun.
_NOUN_DETERMINER = re.compile(
    r"\b(?:un|una|unos|unas|el|del|al|su|sus|mi|mis|tu|tus|este|esta|ese|esa|aquel|aquella|nuestro|nuestra)\s+$"
)
_ELIDED_OBJECT_WORDS = frozenset({
    "ya", "y", "todo", "eso", "esto", "lo", "la", "los", "las", "ahora", "listo", "lista", "hecho", "bien",
    "it", "they", "that", "this", "and", "now", "already", "all", "everything", "done", "just", "successfully",
})


def _claim_names_nothing_else(folded: str, claim: re.Match[str]) -> bool:
    """Only pronouns and adverbs around an actorless claim: its object is what the person just asked for."""

    rest = folded[: claim.start()] + " " + folded[claim.end():]
    return all(word in _ELIDED_OBJECT_WORDS for word in re.findall(r"[a-z]+", rest))


# Fase 3.5 (held-out 2026-09-22): «Reducí el brillo de la pantalla a 45.» with
# no operation. The first person singular preterite is a form, not a list: a
# word ending in a stressed «-é»/«-í» next to a PC object. The future («subiré»,
# «abriré») promises and is not a claim; adverbs and nouns with that ending are
# kept out by name.
_FIRST_PERSON_PRETERITE = re.compile(r"(?<![\w])[a-zñ]{2,}(?:é|í)(?![\w])")
_NOT_A_PRETERITE = frozenset({
    "aquí", "allí", "ahí", "así", "acá", "allá", "café", "bebé", "puré", "josé", "maní", "rubí", "jabalí",
    "esquí", "colibrí", "bisturí", "tabú", "menú", "según", "también", "quizá", "quizás",
    # cien-99 074: «la memoria caché … cuando abres un programa» was read as «caché» (I cached)
    # and the explanation was vetoed. Nouns and demonyms that end in a stressed é/í.
    "caché", "comité", "cliché", "chalé", "canapé", "consomé", "frappé", "té", "qué", "fé",
    "ají", "manatí", "alhelí", "zahorí", "iraní", "iraquí", "israelí", "marroquí", "paquistaní", "saudí",
    "yemení", "sí", "mí",
    # Tanda 2 (2026-09-23): «asegúrate de que el archivo esté en la misma carpeta» is the
    # subjunctive of «estar», not «I …».
    "esté",
})
# Fase 3.5b M35 (real log 121 «¿de qué hablas?» → «…solo respondí a tu mensaje anterior…», vetoed twice and the
# turn asked instead): what BAXY answered, asked or explained TO THE PERSON in this dialogue («te respondí», «respondí a
# tu mensaje») is the conversation itself. Independent review REV2: with «le», a recipient or a channel («respondí el
# correo de tu jefe», «le pregunté por mensaje») it is an effect and stays one.
_SPEECH_ACT_PRETERITES = frozenset({
    "respondí", "contesté", "pregunté", "expliqué", "comenté", "mencioné", "aclaré", "dije", "entendí", "confundí",
})
_SPEECH_ACT_TO_THE_PERSON_BEFORE = re.compile(r"(?<![\w])te\s+$")
_SPEECH_ACT_TO_THE_PERSON_AFTER = re.compile(
    r"^\s+(?:a\s+)?(?:tus?\s+(?:mensajes?|preguntas?|comentarios?)|lo\s+que\s+(?:me\s+)?(?:dijiste|preguntaste)|what\s+you\s+(?:said|asked)|your\s+(?:message|question))(?:\s+anterior)?\b"
)
_EFFECT_CLAIM_NEGATED = re.compile(
    r"\b(?:no|nunca|jamas|jamás|tampoco|sin|ni|not|never|didn'?t|couldn'?t|cannot|can'?t|haven'?t|"
    r"won'?t|don'?t|aun\s+no|aún\s+no|todavia\s+no|todavía\s+no)\b"
)
# (present first person, future first person, gerund) of the irregular ones.
_IRREGULAR_EFFECT_FORMS = {
    "abrir": ("abro", "abriré", "abriendo"),
    "cerrar": ("cierro", "cerraré", "cerrando"),
    "poner": ("pongo", "pondré", "poniendo"),
    "traer": ("traigo", "traeré", "trayendo"),
    "enviar": ("envío", "enviaré", "enviando"),
    "reproducir": ("reproduzco", "reproduciré", "reproduciendo"),
    "encender": ("enciendo", "encenderé", "encendiendo"),
    "recordar": ("recuerdo", "recordaré", "recordando"),
    "pedir": ("pido", "pediré", "pidiendo"),
    "hacer": ("hago", "haré", "haciendo"),
    "corregir": ("corrijo", "corregiré", "corrigiendo"),
    "conseguir": ("consigo", "conseguiré", "consiguiendo"),
    "transferir": ("transfiero", "transferiré", "transfiriendo"),
}
# M139: the world acts are promised in the same forms («te reservo una mesa», «voy a llamar a la pizzería»).
_PROMISED_INFINITIVES = _EFFECT_INFINITIVES + _WORLD_ACT_INFINITIVES
_EFFECT_FORMS = tuple(
    _IRREGULAR_EFFECT_FORMS.get(
        infinitive,
        (infinitive[:-2] + "o", infinitive + "é", infinitive[:-2] + ("ando" if infinitive.endswith("ar") else "iendo")),
    )
    for infinitive in _PROMISED_INFINITIVES
)
_ENCLITIC = r"(?:me|te|se|le|les|nos)?(?:lo|la|los|las)?"
# Uso real 2026-09-23 (tanda 2): what BAXY says he does or will do in a turn that runs
# nothing is as invented as what he says he did: «Se añadirá.», «Claro, te la guardo.» (a
# song), «Te traigo una hamburguesa con queso.», «I'm mostly busy with coding and fixing bugs».
_PROMISED_EFFECT_CLAIM = re.compile(
    r"(?<![\w])(?:"
    # «te la guardo», «ya lo añado», «te traigo una hamburguesa»
    r"(?:(?:me|te|se|le|les|nos)\s+(?:lo|la|los|las)|te|se|le|les|lo|la|los|las|ya|ahora(?:\s+mismo)?|enseguida)\s+"
    + alternation(frozenset(form[0] for form in _EFFECT_FORMS))
    # «lo guardaré», «te lo recordaré», «subiré el volumen»
    + r"|" + alternation(frozenset(form[1] for form in _EFFECT_FORMS))
    # «voy a guardarla», «lo voy a añadir»
    + r"|voy\s+a\s+" + alternation(frozenset(_PROMISED_INFINITIVES)) + _ENCLITIC
    # «estoy guardándola», «te lo estoy añadiendo», «estoy trabajando en eso»
    + r"|estoy\s+(?:\w+\s+)?(?:"
    + alternation(frozenset(form[2] for form in _EFFECT_FORMS))
    + r"|" + alternation(frozenset(form[2].replace("ando", "ándo").replace("iendo", "iéndo") for form in _EFFECT_FORMS))
    + _ENCLITIC + r"|trabajando\s+en)"
    # «I'll add it», «I'm going to save it», «let me look it up», «I'm adding it», «I'm coding»
    + r"|i(?:'ll|\s+will|'m\s+going\s+to|\s+am\s+going\s+to|'m\s+gonna|\s+shall)\s+(?:\w+\s+)?"
    r"(?:add|save|open|close|put|bring|send|delete|remove|install|download|play|mute|unmute|set|schedule|remind|"
    r"note\s+(?:it|that|this)\s+down|jot|write\s+(?:it|that|this)\s+down|order|buy|cook|make\s+you|get\s+you|"
    r"fetch|turn|launch|pause|search|look\s+(?:it|that)\s+up|record|store|create|book|" + _EN_WORLD_ACT_BASE + r")"
    r"|let\s+me\s+(?:add|save|open|close|put|bring|send|delete|remove|install|download|play|mute|set|schedule|"
    r"jot|order|buy|cook|make\s+you|get\s+you|fetch|turn|launch|search|look\s+(?:it|that)\s+up|record|store|"
    r"create|book|" + _EN_WORLD_ACT_BASE + r")"
    r"|i(?:'m|\s+am)\s+(?:\w+\s+)?(?:adding|saving|opening|closing|putting|bringing|sending|deleting|removing|"
    r"installing|downloading|playing|muting|setting|scheduling|reminding|ordering|buying|cooking|fetching|"
    r"turning|launching|searching|recording|storing|creating|booking|coding|fixing|working\s+on|writing\s+code|"
    + _EN_WORLD_ACT_GERUND + r")"
    # Impersonal future: «se añadirá», «quedará guardado», «it will be added»
    r"|se\s+(?:añadir|agregar|guardar|anotar|apuntar|programar|agendar|instalar|descargar|reproducir|"
    r"silenciar|enviar|mandar|borrar|eliminar)án?"
    r"|quedar[áa]n?\s+(?:guardad|añadid|agregad|anotad|apuntad|programad|agendad|instalad|descargad|enviad|"
    r"borrad|eliminad)[oa]s?"
    r"|(?:will|'ll)\s+be\s+(?:added|saved|sent|deleted|removed|installed|downloaded|played|scheduled|stored|"
    r"noted|created)"
    r")(?![\w])"
)
# The assistant's own pastime is invented too: he lives on this PC and does what he is
# asked («I'm mostly busy with coding … when I'm not working on projects»).
_INVENTED_SELF_ACTIVITY = re.compile(
    r"(?<![\w])(?:"
    r"i(?:'m|\s+am)\s+(?:\w+\s+)?(?:busy|occupied)\s+(?:with|doing|working|coding|fixing|on)"
    r"|i\s+(?:\w+\s+)?spend\s+my\s+(?:free\s+|spare\s+)?time"
    r"|in\s+my\s+(?:free|spare)\s+time,?\s+i"
    r"|(?:estoy|ando)\s+(?:\w+\s+)?(?:ocupad[oa]|liad[oa])\s+(?:con|en)"
    r"|(?:paso|dedico)\s+(?:mi|el)\s+tiempo"
    r"|en\s+mi\s+tiempo\s+libre,?\s+(?:me\s+gusta|suelo|hago|paso)"
    r")(?![\w])"
)
# M78 (DEV-D v3l s099 «your speech slower it» → «I speak slowly now.»): how fast or loud BAXY's voice speaks is the
# voice's own setting, which no operation changes; a reply saying it now speaks slower (or will) claims a change
# nothing made. How he words his replies (formal, brief, in Spanish) is his conduct and is not read here. Folded.
_OWN_VOICE_CHANGE = re.compile(
    r"(?<![\w])(?:"
    r"i(?:\s+will|'ll|\s+am\s+going\s+to|'m\s+going\s+to|\s+am\s+now|'m\s+now|\s+now|\s+am|'m)?\s+(?:speak|talk)(?:ing)?|"
    r"(?:ahora\s+|ya\s+)?(?:hablo|hablare|voy\s+a\s+hablar(?:te)?|estoy\s+hablando(?:te)?|te\s+hablo|te\s+hablare)"
    r")\s+(?:\w+\s+){0,2}?(?:(?:mas|more|less|menos|a\s+bit|un\s+poco|much)\s+)?"
    r"(?:slow(?:ly|er)?|fast(?:er)?|quick(?:ly|er)?|loud(?:ly|er)?|soft(?:ly|er)?|quiet(?:ly|er)?|"
    r"despacio|lento|lentamente|rapido|rapidamente|deprisa|alto|fuerte|suave|bajito)"
    r"(?![\w])"
)
# What BAXY says to the person is the conversation itself: «te pongo un ejemplo», «te
# traigo una curiosidad», «let me bring you a fun fact».
_SPOKEN_OBJECT = re.compile(
    # «haré lo posible» is a manner of speaking, not an effect.
    r"\s+lo\s+(?:posible|mejor|que\s+pueda)\b|"
    r"\s+(?:(?:un|una|unos|unas|el|la|los|las|otro|otra|algun[oa]?|you|an?|the|some|another)\s+)*"
    r"(?:(?:fun|quick|little|pequeñ[oa]|breve)\s+)?"
    r"(?:ejemplos?|curiosidad(?:es)?|datos?|chistes?|respuestas?|resumen|ideas?|consejos?|saludos?|abrazos?|"
    r"besos?|explicaci[oó]n|recetas?|historias?|cuentos?|poemas?|frases?|citas?|noticias?|"
    r"recomendaci[oó]n(?:es)?|opci[oó]n(?:es)?|sugerencias?|preguntas?|trucos?|tips?|"
    r"examples?|jokes?|facts?|answers?|summary|stories|story|poems?|quotes?|recipes?|suggestions?|options?)\b"
)
# «si quieres, te lo recuerdo», «I'll add it if you want»: an offer under a condition.
_CONDITIONAL_OFFER = re.compile(r"\b(?:si|if|cuando|when|once|en\s+cuanto|apenas|as\s+soon\s+as)\b")


def visible_reply_claims_an_effect(value: object, request: object = "") -> bool:
    """Reject a conversation reply that claims an effect no operation produced.

    Owner's test 2026-09-21, turn 189: «Pero quiero que le hagas click» was
    answered «Claro, ya le hice click.» with zero operations. A conversation
    turn executes nothing by construction, so BAXY's completed act on the
    person's world in it is invented every time, in any tense the verb tables
    above generate. Negated forms («no lo hice», «no pude abrirlo») are the
    honest reply and survive; general knowledge in the third person («Romero
    publicó…», «la fábrica se cerró en 1990») is untouched.

    Uso real 2026-09-23 (tanda 2): nothing runs after the reply either, so an
    effect done now or promised («te la guardo», «se añadirá», «I'll add it»)
    and the assistant's own invented pastime are the same claim. A question
    («¿lo añado?»), an offer under a condition («si quieres, te lo recuerdo»)
    and what he says to the person («te pongo un ejemplo») are not.

    A label that says back the person's own word («listo» → «¡Listo!») agrees
    with them, and a preterite after a determiner is a noun («un traje»).
    """

    text = str(value or "").strip()
    if not text:
        return False
    asked_words = set(re.findall(r"[a-z]+", _accent_folded_with_punctuation(request).casefold()))
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", text.casefold()):
        folded = _accent_folded_with_punctuation(sentence)
        world = _PERSON_WORLD.search(folded) is not None
        claims = [
            (sentence, match)
            for match in _DONE_BY_BAXY.finditer(sentence)
            if _NOUN_DETERMINER.search(sentence[: match.start()]) is None
        ]
        claims.extend((folded, match) for match in _DONE_BY_BAXY_FOLDED.finditer(folded))
        claims.extend(
            (folded, match)
            for match in _DONE_WITHOUT_ACTOR.finditer(folded)
            if world or _claim_names_nothing_else(folded, match)
        )
        if world:
            claims.extend(
                (sentence, match)
                for match in _FIRST_PERSON_PRETERITE.finditer(sentence)
                if match.group(0) not in _NOT_A_PRETERITE
                and not (
                    match.group(0) in _SPEECH_ACT_PRETERITES
                    and (
                        _SPEECH_ACT_TO_THE_PERSON_BEFORE.search(sentence[: match.start()]) is not None
                        or _SPEECH_ACT_TO_THE_PERSON_AFTER.match(sentence[match.end():]) is not None
                    )
                )
                and not match.group(0).endswith(("aré", "eré", "iré"))
            )
        if "?" not in sentence and "¿" not in sentence:
            claims.extend(
                (folded, match)
                for match in _STATUS_LABEL.finditer(folded)
                if not set(re.findall(r"[a-z]+", match.group(0))) <= asked_words
            )
            claims.extend((sentence, match) for match in _INVENTED_SELF_ACTIVITY.finditer(sentence))
            claims.extend((folded, match) for match in _OWN_VOICE_CHANGE.finditer(folded))
            if _CONDITIONAL_OFFER.search(sentence) is None:
                claims.extend((sentence, match) for match in _PROMISED_EFFECT_CLAIM.finditer(sentence))
        for source, match in claims:
            # What BAXY says to the person is the conversation, not an effect («te hice una pregunta»).
            if _SPOKEN_OBJECT.match(source[match.end():]) is not None:
                continue
            # A negation earlier in the same clause makes it a denial, not a claim.
            clause = source[:match.start()]
            for boundary in (",", ";", " pero ", " but ", " aunque "):
                if boundary in clause:
                    clause = clause.rsplit(boundary, 1)[-1]
            # «lo que hice fue decir la verdad»: a pseudo-cleft describes the act
            # it names; it does not claim that an effect happened.
            cleft = re.match(r"\s*(?:fue|es|era)\s+(?P<act>[a-záéíóúñ]+)(?P<rest>[^.!?]*)", source[match.end():])
            if (
                re.search(r"\blo que\s+(?:(?:ya|solo|sólo)\s+)?$", source[:match.start()])
                and cleft is not None
                and not (
                    re.search(r"(?:ar|er|ir)$", cleft.group("act"))
                    and re.search(r"(?<![\w])" + _PC_OBJECT + r"(?![\w])", cleft.group("rest"))
                )
            ):
                continue
            # «I will not open any programs»: the negation can sit inside the promise itself.
            if _EFFECT_CLAIM_NEGATED.search(clause + match.group(0)) is None:
                return True
    return False


# M45 (FINAL 2026-09-28, t22): «cancelar» after the question for «Reanudar el ejercicio en 5 minutos, mejor en 10»
# was composed «Reanudaré el ejercicio en 10 minutos.» with no call to the Core; the same situation gave «The room is
# now darker. …» (t20) and «La nueva lista se ha creado…» (t42). A cancelled clarification ran nothing and leaves
# nothing pending: each statement says the drop or a negation, and an acknowledgement word may lead it.
_CANCELLATION_WORDS = re.compile(
    r"(?<![\w'])(?:cancel\w*|anul\w*|olvid\w*|descart\w*|(?:lo|la|eso|esto)\s+dej\w*|dejemos\w*|dejamos\w*|"
    r"dejado|dejarlo|nada|ningun\w*|no|ni|nunca|sin\s+(?:cambios?|hacer|tocar|efecto)|"
    r"not|nothing|none|never|no\s+longer|drop\w*|forget\w*|forgot\w*|(?:leave|leaving|left)\s+(?:it|that|this)|"
    r"won'?t|don'?t|didn'?t|stop\w*|abort\w*|scrap\w*|skip\w*)(?![\w'])"
)
_ACKNOWLEDGEMENT_CLAUSE = re.compile(
    r"(?:vale|ok|okay|okey|de\s+acuerdo|entendido|entiendo|perfecto|listo|claro|bien|muy\s+bien|bueno|"
    r"sure|alright|all\s+right|got\s+it|understood|fine|no\s+problem|sin\s+problema)"
)
_CLAUSE_BREAK = re.compile(
    r"\s*[,;:—–]\s*|\s+(?:y|e|pero|aunque|asi\s+que|así\s+que|entonces|and|but|so|then|although)\s+"
)
# A promise inside a clause that also names the drop: «cancelado, reanudaré…» is split above; «reanudaré el
# ejercicio si no quieres otra cosa» carries «no» and still promises the cancelled effect.
_FIRST_PERSON_PROMISE = re.compile(
    r"(?<![\w])(?:[a-zñ]+(?:aré|eré|iré)|(?:pond|tend|sald|vend|pod|sab|querr|cab)ré|diré|"
    r"i'll|i\s+will|i(?:'m|\s+am)\s+going\s+to|voy\s+a|let\s+me)(?![\w])"
)


def cancelled_clarification_defect(text: object) -> str:
    """Veto a composed cancellation that states or promises the effect it cancelled (M45)."""

    acknowledged = False
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", str(text or "").strip().casefold()):
        if "?" in sentence or "¿" in sentence:
            # «¿Quieres otra cosa?» offers, it does not claim.
            continue
        for clause in _CLAUSE_BREAK.split(sentence):
            clause = clause.strip(" .!¡…\"'«»“”()")
            if not clause:
                continue
            folded = _accent_folded_with_punctuation(clause)
            if _ACKNOWLEDGEMENT_CLAUSE.fullmatch(folded) is not None:
                continue
            if _CANCELLATION_WORDS.search(folded) is None:
                return "cancelled_effect_claim"
            promise = _FIRST_PERSON_PROMISE.search(clause)
            if promise is not None and _EFFECT_CLAIM_NEGATED.search(clause[: promise.start()]) is None:
                return "cancelled_effect_claim"
            acknowledged = True
    return "" if acknowledged else "cancelled_effect_claim"


_PERSONAL_RECORD_CONTENT = re.compile(
    r"\b(?:hay|tienes|tenes|tiene|contiene|incluye|figuran?|aparecen?|esta|estan|queda|quedan|"
    r"there\s+(?:is|are)|there's|you\s+have|you've\s+got|has|contains|includes|"
    r"(?:is|are|isn't|aren't)(?:\s+not)?\s+(?:on|in)|is\s+empty)\b"
)
# A record named as the person's may not be given any state at all: «tu pedido llegó», «your order is ready».
_OWNED_RECORD_STATE = re.compile(r"\b(?:es|son|fue|llego|llegaron|is|are|was|were|arrived|shipped)\b")
_UNREAD_RECORD_HONESTY = re.compile(
    r"\b(?:no\s+(?:se|puedo|pude|tengo\s+acceso|consigo|lo\s+se)|sin\s+(?:leer|revisar|mirar|ver|acceso)|"
    r"puedo\s+(?:leer|revisar|buscar|mirar|ver|consultar)|don'?t\s+know|do\s+not\s+know|can(?:not|'t)|"
    r"no\s+access|unable|not\s+able|without\s+(?:reading|checking|looking)|can\s+(?:check|read|look)|"
    r"(?:don'?t|do\s+not)\s+have\s+access)\b"
)
# «En tu calendario hay una opción para…» describes an application, not its content.
_APPLICATION_FEATURE = re.compile(
    r"\b(?:opcion|opciones|funcion|funciones|boton|seccion|menu|pestana|apartado|ajuste|"
    r"option|feature|button|setting|section|menu|tab)\b"
)
# The person as the one who holds something now: «Ya tienes en la lista: …», «No tienes nada programado»,
# «You haven't set anything right now.» (tanda 7b, with two timers running). «Tienes que…», «you have to…»
# say what to do, not what there is.
_PERSON_HOLDS = re.compile(
    r"^\W*(?:(?:si|yes|yeah|no|ya|todavia|aun|still|also|tambien|ahora|now|actualmente|currently|hoy|today|"
    r"right\s+now|por\s+ahora|so\s+far|hasta\s+ahora)\b[\s,]*)*"
    r"(?:no\s+)?(?:tienes|tenes|te\s+quedan?|has"
    r"|you(?:'ve|\s+have|\s+haven't|\s+have\s+not|\s+don't\s+have|\s+do\s+not\s+have|'ve\s+got|\s+got|"
    r"\s+still\s+have|\s+already\s+have|\s+currently\s+have))\b(?!\s+(?:que|to)\b)"
)
# What the person set up, said of them: every effect participle but «hecho» («has hecho una buena pregunta»).
_CONFIGURED_STATE = re.compile(
    r"(?<![\w])(?:(?!hech)" + _ES_PARTICIPLE + r"|" + alternation(frozenset(_EN_DONE)) + r")(?![\w])"
)
_PERSONAL_STORE_QUALIFIERS = frozenset({
    "la", "las", "compra", "compras", "tareas", "pendientes", "cosas", "super", "supermercado", "mercado",
})


def visible_reply_asserts_unread_personal_records(
    value: object, request: object = "", prior_requests: tuple[str, ...] = (),
) -> bool:
    """Reject a conversation reply that states what the person's lists, notes, alarms,
    timers, agenda, mail or orders hold: nothing was read in a conversation turn.

    The store is the person's when the reply says so («tu lista», «your order»), when the
    person is the one who holds it («Ya tienes en la lista: …», «You haven't set anything»),
    or when it names with an article a store the person named as theirs in this dialogue
    («apúntame en la lista de la compra» → «En la lista hay …»). Saying it cannot know, a
    question, a hypothesis and general knowledge about lists («una lista de la compra
    suele…», «la lista de Schindler tiene…») survive.
    """

    text = str(value or "").strip()
    if not text:
        return False
    owned_by_the_person = any(names_an_own_record_store(item) for item in (request, *prior_requests))
    for said in re.split(r"(?<=[.!?…])\s+|\n+", text.casefold()):
        # «sí» agrees; only «si» opens a hypothesis, so the accents are read first.
        if "?" in said or "¿" in said or _CONDITIONAL_OFFER.search(said) is not None:
            continue
        sentence = _accent_folded_with_punctuation(said)
        if _UNREAD_RECORD_HONESTY.search(sentence) is not None or _APPLICATION_FEATURE.search(sentence) is not None:
            continue
        store = re.search(rf"\b{_PERSONAL_RECORD_STORE}\b", sentence)
        if _PERSON_HOLDS.search(sentence) is not None and (
            store is not None or _CONFIGURED_STATE.search(sentence) is not None
        ):
            return True
        possessed = re.search(rf"\b(?:tu|tus|your)\s+(?:[\w-]+\s+)?{_PERSONAL_RECORD_STORE}\b", sentence)
        if possessed is not None and (
            _PERSONAL_RECORD_CONTENT.search(sentence) is not None
            or _OWNED_RECORD_STATE.search(sentence[possessed.end():]) is not None
        ):
            return True
        if owned_by_the_person and _PERSONAL_RECORD_CONTENT.search(sentence) is not None:
            for named in re.finditer(
                rf"\b(?:la|las|el|los|the)\s+(?:(?:shopping|grocery|to-?do)\s+)?{_PERSONAL_RECORD_STORE}\b"
                r"(?:\s+(?:de|del|of)\s+(?P<qualifier>[\w-]+))?",
                sentence,
            ):
                if named.group("qualifier") in (None, *_PERSONAL_STORE_QUALIFIERS):
                    return True
    return False


_POLAR_ANSWER = re.compile(
    r"^\W*(?:sí\b|si,|yes\b|yeah\b|yep\b|yup\b|correcto\b|correct\b|exacto\b|exactly\b|así\s+es\b|"
    r"that's\s+right\b|no[,.!]|no$|nope\b|not\s+yet\b|todavía\s+no\b|aún\s+no\b)"
)


def visible_reply_answers_an_unobserved_polar_question(value: object, request: object = "") -> bool:
    """Reject «Sí»/«No» to whether something of the person's is so, with nothing observed.

    Uso real 2026-09-25 (tanda 8): «está mi orden lista para recoger ya» was answered «Sí,
    está lista para recoger.»; BAXY knows nothing of any order. The honest reply says it
    cannot know or has no access («No, no puedo saberlo desde aquí» survives).
    """

    text = str(value or "").strip()
    if not text or _POLAR_ANSWER.search(text.casefold()) is None:
        return False
    if not asks_a_polar_question_about_the_person(request):
        return False
    honest = _accent_folded_with_punctuation(text).casefold()
    return _UNREAD_RECORD_HONESTY.search(honest) is None and not _unsupported_answer_has_inability(text)


# M79 (DEV-D v3m p24-t5 «That is confirmed to proceed.» → «The plan is confirmed to proceed.», with nothing played): a
# conversation turn runs nothing, so a plan, an order or a request said to be confirmed, approved or under way is a
# settled effect nobody made. Folded; a question or an offer under a condition is not a claim.
_SETTLED_PLAN = re.compile(
    r"\b(?:(?:the|your|this|that|it|everything|all)\s+(?:(?:plan|order|request|booking|reservation|purchase|playback|"
    r"movie|search)\s+)?(?:is|has\s+been|was|are|have\s+been)\s+(?:now\s+|all\s+)?(?:confirmed|approved|underway|"
    r"in\s+progress|on\s+its\s+way)|(?:is\s+)?confirmed\s+to\s+(?:proceed|go\s+ahead|start)|"
    r"(?:el|tu|este|ese|la)?\s*(?:plan|pedido|reserva|solicitud|compra|todo|eso)\s+(?:ya\s+)?(?:esta|queda|quedo|fue|"
    r"ha\s+sido)\s+"
    r"(?:ya\s+)?(?:confirmad[oa]|aprobad[oa]|en\s+marcha|en\s+curso)|"
    # M85 (DEV-D v3o p24-t5 «Confirmed, the procedure will proceed.» with nothing played): the settlement said as the
    # sentence's own opening word, and the plan, procedure or request said to go ahead from now on.
    r"^\W*(?:confirmed|approved|confirmad[oa]|aprobad[oa])\b(?!\s+(?:that|by|que|por)\b)|"
    r"(?:the|your|this|that|it|el|tu|este|ese|la|lo)\s+(?:(?:plan|procedure|process|order|request|operation|playback|"
    r"booking|purchase|action|task|step|procedimiento|proceso|operacion|reproduccion|pedido|solicitud|reserva|compra|"
    r"accion|tarea|paso)\s+)?"
    r"(?:(?:will|shall)\s+(?:now\s+)?|(?:is|are)\s+(?:now\s+)?(?:going\s+to\s+)?)(?:proceed(?:ing)?|go(?:ing)?\s+ahead)|"
    r"(?:el|la|tu|este|ese|esta)\s+(?:plan|procedimiento|proceso|pedido|solicitud|operacion|reproduccion|reserva|"
    r"compra|accion|tarea|paso)\s+(?:se\s+)?(?:procedera|seguira\s+adelante|va\s+a\s+(?:proceder|seguir\s+adelante))|"
    # M105 (DEV-D v4a D-p24-t5 «That is confirmed to proceed.» → «I confirm the action will proceed.» with nothing run, the
    # same words M88 met after a reply that asked nothing; here the reply before had asked a question): BAXY's own
    # confirmation that an act goes ahead, and the act promised as BAXY's next step, in a turn that runs nothing.
    r"(?:\bi\s+(?:hereby\s+)?confirm|\b(?:te\s+|le\s+|se\s+)?confirmo)\b.*?\b(?:will|shall|going\s+to|proceed\w*|"
    r"go(?:es|ing)?\s+ahead|start\w*|begin\w*|procedera|procedere|seguira|se\s+hara|se\s+realizara|en\s+marcha)|"
    r"\bi(?:'ll|\s+will|\s+am\s+going\s+to)\s+(?:now\s+)?proceed\b|\bprocedere\b|\bprocedo\s+(?:a|con)\b)\b"
)
# M79 (DEV-D v3m p27-t4/t5 «I don't have any movies featuring Eugene Dynarski in my database.»): BAXY has no database,
# catalog or records of his own to look things up in; saying so invents where an answer would come from. Folded.
_OWN_STORE = re.compile(
    r"\b(?:in|on|from|en|de)\s+(?:my|mi|mis)\s+(?:own\s+)?(?:database|data\s*base|data|knowledge\s+base|records?|"
    r"catalog(?:ue)?|files|base\s+de\s+datos|base\s+de\s+conocimientos?|registros?|catalogo|archivos|datos)\b"
)


def visible_reply_settles_a_plan(value: object, request: object = "") -> bool:
    """A plan or order said to be confirmed or under way in a turn that ran nothing (see above)."""

    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", str(value or "")):
        if "?" in sentence or "¿" in sentence:
            continue
        folded = _reading_fold(sentence)
        if _CONDITIONAL_OFFER.search(folded) is None and _SETTLED_PLAN.search(folded) is not None:
            return True
    return False


# M85 (DEV-D v3o D-p09-t3 «never mind do not add barbells to my fitness list» → «I did not add barbells to your fitness
# list.» right after adding them; D-w01-t2 «oye y cuánta sal le echo al agua» → «No he añadido sal al agua.»): a turn that
# ran nothing has no write of its own to deny either, unless the person asked about that act or for it
# (semantic.conversation.request_names_the_act), or the denial says why («No lo añadí: no leí tu lista.»).
_DENIAL_REASON = re.compile(r"^[^.!?]*?(?::|;|\bporque\b|\bya\s+que\b|\bpues\b|\bbecause\b|\bsince\b)\s*\S")


def visible_reply_denies_an_own_write(value: object, request: object = "") -> bool:
    """A write told as not done («I did not add», «No he añadido»), bare, in a reply to something that did not ask
    about it nor for it."""

    folded = _reading_fold(str(value or ""))
    denied = next(
        (
            found for found in _NEGATED_OWN_WRITE.finditer(folded)
            # A failed attempt («no pude», «I couldn't») is the failure checks' (asserted_failure), not a denial.
            if re.search(r"\b(?:pude|could|couldn'?t|able)\b", found.group(0)) is None
        ),
        None,
    )
    if denied is None or _DENIAL_REASON.search(folded[denied.end():]) is not None:
        return False
    # M88 (DEV-D v3r D-p24-t5): a go-ahead asks for the act, so saying it was not done answers it.
    return not (
        request_names_the_act(str(request or ""), denied.group(0).split()[-1])
        or dialogue_slot.gives_go_ahead(str(request or ""))
    )


# M85 (DEV-D v3o D-p27-t1 «Any good movies for me to watch?» → «You should check out the latest sci-fi flick about time
# travel, it's really gripping.», with nothing read): a work recommended or called new with no title is a work nobody can
# find; it stands for a real one only by its name. Folded.
_WORK_NOUN = (
    r"(?:movies?|films?|flicks?|series|shows?|documentar(?:y|ies)|books?|novels?|songs?|albums?|games?|"
    r"peliculas?|pelis?|series|documentales?|libros?|novelas?|canciones|cancion|temas?|discos?|albumes|album|juegos?)"
)
_UNNAMED_WORK_FRAME = re.compile(
    r"\b(?:check\s+out|you\s+(?:should|could|might|must|would)\s+(?:(?:really|definitely)\s+)?(?:watch|see|read|try|"
    r"listen\s+to|play|enjoy|like|love)|i\s+(?:would\s+)?(?:recommend|suggest)|(?:te|le|les)\s+(?:recomiendo|"
    r"recomendaria|sugiero)|(?:deberias|podrias)\s+(?:ver|leer|escuchar|jugar|probar)|"
    r"(?:the|a|an|la|el|una|un)\s+(?:(?:very|really|muy)\s+)?(?:latest|newest|new|recent|brand\s+new|nuev[oa]|"
    r"ultim[oa]|reciente))\b"
)


_UNNAMED_WORK_HINT = {
    "es": "No leíste qué se estrena ni qué es nuevo: si recomiendas, nombra por su título, entre comillas, obras que "
    "conozcas, sin decir que son nuevas, recientes ni las últimas. Una o dos frases.",
    "en": "You read nothing about what is new or out now: if you recommend, name works you know by their title, in "
    "quotation marks, without calling them new, recent or the latest. One or two sentences.",
}


# M105 (DEV-D v4a D-p28-t3).
_UNREAD_SHOWTIMES_HINT = {
    "es": "No leíste la cartelera: no digas qué película dan en un cine ni a qué hora. Si es lo que la persona quiere "
    "saber, di llanamente que no tienes comprobada la cartelera. Una frase.",
    "en": "You read no listing: do not say which film a cinema shows or at what time. If that is what the person "
    "wants, say plainly that you have not checked the showtimes. One sentence.",
}


def visible_reply_recommends_an_unnamed_work(value: object) -> bool:
    """A sentence that recommends, or calls new, a work (a movie, a book, a song) without naming any."""

    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", str(value or "").strip()):
        if "?" in sentence or "¿" in sentence or re.search(
            r"[\"«“][^\"»”]+[\"»”]|‘[^’]+’|(?<!\w)'[^']+'(?!\w)", sentence,
        ):
            continue
        folded = _reading_fold(sentence)
        frame = _UNNAMED_WORK_FRAME.search(folded)
        if frame is None or re.search(rf"\b{_WORK_NOUN}\b", folded) is None:
            continue
        # A title: a capitalized word that is not the sentence's first, nor «I» / «BAXY».
        words = re.findall(r"[^\W\d_][\w'’-]*", sentence)
        if not any(word[:1].isupper() and word not in {"I", "BAXY"} for word in words[1:]):
            return True
    return False


# M105 (DEV-D v4a D-p28-t3 «Hustlers is perfect.» after «Look for movies in Union City.» → «Hustlers is playing at the
# Union City theater.», with nothing read): what a cinema shows, and when, is today's listing; a turn that read none
# cannot state it. Folded.
_SHOWTIME_CLAIM = re.compile(
    r"\b(?:is|are)\s+(?:now\s+|currently\s+|still\s+)?(?:playing|showing|screening|on\s+screen)\s+(?:at|in)\b|"
    r"\b(?:now|currently)\s+(?:playing|showing|screening)\b|\bin\s+theaters?\s+(?:now|today|tonight)\b|"
    r"\bshowtimes?\s+(?:are|is|at|for|include)\b|\bshows?\s+at\s+\d|\bscreenings?\s+at\s+\d|"
    r"\b(?:esta|estan|sigue|siguen)\s+en\s+(?:cartelera|cartel|el\s+cine|los\s+cines|cines)\b|"
    r"\b(?:se\s+)?(?:exhibe|exhiben|proyecta|proyectan|estrena|estrenan|dan|da)\s+en\s+(?:el\s+|los\s+|la\s+)?"
    r"(?:cine|cines|sala|salas|cinemark|cinepolis|teatro)\b|\b(?:hay\s+)?funcion(?:es)?\s+(?:a|de)\s+las\s+\d"
)
# Not knowing it, not having read it, or offering to look it up claims no listing.
_SHOWTIME_HEDGE = re.compile(
    r"\b(?:no|not|nunca|never|sin|si|if|whether|unless|puedo\s+buscar|could\s+look|can\s+look|can\s+check)\b|n't\b"
)
_CINEMA_CONTEXT = re.compile(
    r"\b(?:movies?|films?|theaters?|theatres?|cinemas?|cinemark|cineplex|imax|xd|showtimes?|screenings?|cine|cines|"
    r"peliculas?|cartelera|funcion(?:es)?|estreno)\b"
)


def visible_reply_claims_unread_showtimes(
    value: object, request: object = "", prior_requests: tuple[str, ...] = (),
) -> bool:
    """A film said to be showing at a cinema, or its showtimes given (see above), in a conversation about films or
    cinemas, by a turn that read no listing."""

    folded = _reading_fold(str(value or ""))
    claimed = any(
        _SHOWTIME_CLAIM.search(sentence) is not None and _SHOWTIME_HEDGE.search(sentence) is None
        for sentence in re.split(r"(?<=[.!?…])\s+|\n+", folded)
        if "?" not in sentence
    )
    if not claimed:
        return False
    # The reply's own words, or the person's (semantic.web.talks_of_films), speak of films or cinemas.
    return _CINEMA_CONTEXT.search(folded) is not None or talks_of_films(str(request or ""), *prior_requests)


# M105 (DEV-D v4a D-p23-t5 «Actually do English subtitles.» → «I can add English subtitles to your videos.», right after
# «I do not add subtitles to movies.»): a turn that ran nothing claims it can do the act asked. What BAXY does is the
# catalog's, and a turn that does none of it has no ground for «I can»: either the act is not served (a false
# capability) or it was not done (an empty offer standing for the act). Folded; a question, a condition or a denial is
# not such a claim, and neither is what BAXY says, writes or explains in the conversation itself.
_CLAIMED_ABILITY = re.compile(
    r"(?<!\bno\s)(?<!\bnot\s)\b(?:i\s+can|i\s+am\s+able\s+to|i'?m\s+able\s+to|i\s+could|puedo|podria|soy\s+capaz\s+de)"
    r"\s+(?:also\s+|now\s+|tambien\s+|ahora\s+)?(?:add|put|turn|set|enable|activate|switch|change|play|install|download|"
    r"subtitle|record|book|order|buy|anadir|agregar|anadirle|agregarle|poner|ponerle|activar|encender|apagar|cambiar|"
    r"reproducir|instalar|descargar|grabar|reservar|comprar|pedir)\b"
)


def visible_reply_claims_an_unrun_ability(value: object, request: object = "") -> bool:
    """An act said to be within BAXY's reach (see above) in a turn that ran nothing; not when the person asked what
    BAXY can do, which the capability answer gives."""

    if asks_whether_able(str(request or "")) or _looks_like_capability_question(str(request or "")):
        return False
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", str(value or "")):
        if "?" in sentence or "¿" in sentence:
            continue
        folded = _reading_fold(sentence)
        if _CONDITIONAL_OFFER.search(folded) is None and re.search(r"\b(?:if|si|cuando|when)\b", folded) is None and (
            _CLAIMED_ABILITY.search(folded) is not None
        ):
            return True
    return False


def _claimed_ability_instruction(last_said: str, language: str | None) -> str:
    """M109 (DEV-D v4d D-p23-t5 «Actually do English subtitles.» after «I do not add subtitles to movies.»): the M105
    hint told the writer «say plainly that you have not done it», and the bare «I did not add English subtitles to the
    movie.» it then wrote died as own_write_denied twice; the turn had no final. The hint now says what to write that
    every veto accepts: the limit said again in other words, or the act not done with its reason after a colon (a
    denial that says why is no bare denial), with BAXY's last message as the data that reason comes from."""

    last = " ".join(str(last_said or "").split())[:320]
    if language == "en":
        return (
            "You did nothing in this turn: do not say you can do it"
            + (f". Your last message was «{last}»" if last else "")
            + ". In one sentence, either say again in other words that you do not do that, if your last message says "
            "so, or say that you have not done it and why, after a colon («I have not done that: …»)."
        )
    return (
        "En este turno no hiciste nada: no digas que puedes hacerlo"
        + (f". Tu último mensaje fue «{last}»" if last else "")
        + ". En una frase, o di de nuevo con otras palabras que eso no lo haces, si tu último mensaje lo dice, o di que "
        "no lo has hecho y por qué, tras dos puntos («No lo he hecho: …»)."
    )


def _own_write_denied_instruction(language: str | None) -> str:
    """M85's hint for a bare denial of a write (DEV-D v3o D-p09-t3, D-w01-t2), with (M109, DEV-D v4d D-p23-t5) what to
    write when the person did ask for the act: «do not say what you did or did not do» left no answer to «Actually do
    English subtitles.», and its accumulation with the claimed-ability hint contradicted it."""

    if language == "en":
        return (
            "Nothing ran this turn: a bare «I did not …» answers nothing. Answer, in one sentence, what the person says "
            "or asks, with what the conversation shows; if they asked you to do something, say that you do not do it, "
            "or that you have not done it and why, after a colon («I have not done that: …»)."
        )
    return (
        "En este turno no se ejecutó nada: un «no lo hice» a secas no contesta nada. Contesta, en una frase, lo que la "
        "persona dice o pregunta, con lo que muestra la conversación; si te pidió hacer algo, di que eso no lo haces, "
        "o que no lo has hecho y por qué, tras dos puntos («No lo he hecho: …»)."
    )


# M109 (DEV-D v4d D-p23-t5, D-p24-t5): a talk reply that tells a failure («I cannot add English subtitles to the
# movie.», «I cannot sign you in…») is refused by the App's conversation policy (looks_like_failure), whose fallback
# then composes with no conversation at all. The writer is told what to say instead, before the App sees it.
_TOLD_FAILURE_HINT = {
    "es": "No lo cuentes como algo que no pudiste o no puedes hacer: sin «no puedo», «no pude» ni «falló». Si es algo "
    "que no haces, dilo en presente («No …»); si todavía no está hecho, di que no lo has hecho y por qué, tras dos "
    "puntos («No lo he hecho: …»). Una frase con tus palabras, sin repetir tu mensaje anterior.",
    "en": "Do not tell it as something you could not or cannot do: no «cannot», «can't», «could not» or «failed». If it "
    "is something you do not do, say so in the present («I don't …»); if it is not done yet, say that you have not done "
    "it and why, after a colon («I have not done that: …»). One sentence of your own, not your previous message again.",
}


def visible_reply_claims_an_own_store(value: object, request: object = "") -> bool:
    """BAXY speaks of a database, catalog or records of his own (see above), unless the person named it."""

    found = _OWN_STORE.search(_reading_fold(str(value or "")))
    return found is not None and found.group(0) not in _reading_fold(str(request or ""))


def _go_ahead_reply_unmet(reply: str, request: str) -> bool:
    """Whether a reply to a go-ahead nothing was waiting for (M88) fails it: it must say it was not done, and (M105,
    DEV-D v4a D-p24-t4 «Yes, do it for me.» after a Netflix sign-in failure → «I have not done it yet because the
    streaming of Hustlers failed because…», refused as a failure told in talk, and the App fell back to «What specific
    detail is missing…?») it must not tell that as a failure, which the App's conversation policy refuses."""

    return (
        not dialogue_slot.says_nothing_was_done(reply)
        or talk_reply_tells_a_failure(reply, request)
        # M118 (cien-113 048 «haz eso» after «keep chatting without opening apps» → «No lo he hecho: no tengo la
        # capacidad de mantener conversaciones sin abrir aplicaciones.»): talking is what BAXY is doing; a limit on it
        # is false whatever the last message said.
        or _DENIES_TALKING.search(_reading_fold(reply)) is not None
    )


_DENIES_TALKING = re.compile(
    r"\bno\s+(?:tengo\s+(?:la\s+)?(?:capacidad|posibilidad)\s+de|puedo|se|soy\s+capaz\s+de)\s+(?:mantener\s+|tener\s+|seguir\s+)?"
    r"(?:una\s+|la\s+)?(?:conversa\w*|hablar|charlar|chatear)"
    r"|\b(?:can'?t|cannot|can\s+not|am\s+not\s+able\s+to|(?:do\s+not|don'?t)\s+have\s+the\s+(?:ability|capacity)\s+to)\s+"
    r"(?:have\s+|keep\s+|hold\s+|carry\s+on\s+)?(?:a\s+)?(?:conversations?|chat\w*|talk\w*)"
)


def _go_ahead_instruction(last_said: str, language: str | None) -> str:
    """M88 (DEV-D v3r D-p24-t5): what the writer of a go-ahead that nothing was waiting for is told before it writes —
    the fact the three drafts lacked: nothing ran this turn, nothing was waiting for that yes, and what BAXY last
    said (whose outcome, a failure included, is the only reason it may give)."""

    last = " ".join(str(last_said or "").split())[:320]
    # M109 (DEV-D v4d D-p24-t5): after a question of BAXY's the go-ahead answers nothing it asked.
    asked = last.endswith("?")
    if language == "en":
        return (
            "The person tells you to go ahead, but nothing ran this turn and "
            + ("their yes does not answer what you asked" if asked else "nothing of yours was waiting for a yes")
            + (f"; your last message was «{last}»" if last else "")
            + ". In one sentence, say that you have not done it yet and, if your last message says why, give that "
            # M105 (DEV-D v4a D-p24-t4): «…because the streaming of Hustlers failed because…» was refused as a failure.
            "reason as what is still needed (for example, that the service asks to sign in on this PC first), without "
            "the words failed, could not or cannot. Never say it is confirmed, under way or will proceed."
        )
    return (
        "La persona te dice que sigas adelante, pero en este turno no se ejecutó nada y "
        + ("su sí no contesta lo que preguntaste" if asked else "nada tuyo esperaba un sí")
        + (f"; tu último mensaje fue «{last}»" if last else "")
        + ". En una frase, di que todavía no lo hiciste y, si tu último mensaje dice por qué, da ese motivo como lo "
        "que aún falta (por ejemplo, que el servicio pide iniciar sesión en este PC antes), sin las palabras falló, "
        "no pude ni no puedo. Nunca digas que está confirmado, en marcha o que se hará."
    )


def _call_off_instruction(last_said: str, language: str | None) -> str:
    """M99 (DEV-D v3x D-p01-t3 «no, cancel» after a search that had already answered → «I have cancelled the Christmas
    list search.», «I cannot cancel tasks or lists…», then «I will not proceed with the cancellation.»): the person
    calls off what they asked; nothing of it is running and nothing runs now. The writer is told so, with BAXY's last
    message, and acknowledges it."""

    last = " ".join(str(last_said or "").split())[:320]
    if language == "en":
        return (
            "The person calls off what they asked just before. Nothing of it is running and nothing runs now"
            + (f"; your last message was «{last}»" if last else "")
            + ". Acknowledge it in one short sentence: you leave it there. Do not say you cancelled, undid or "
            "stopped anything, and do not say you cannot cancel."
        )
    return (
        "La persona deja sin efecto lo que pidió justo antes. Nada de eso está en curso y ahora no se ejecuta nada"
        + (f"; tu último mensaje fue «{last}»" if last else "")
        + ". Acéptalo en una frase corta: lo dejas ahí. No digas que cancelaste, deshiciste o detuviste algo, ni "
        "que no puedes cancelar."
    )


def conversation_world_claim(value: object, request: object = "", prior_requests: tuple[str, ...] = ()) -> str:
    """Why a reply written with no operation run claims something of the person's world, or "".

    Nothing ran and nothing was read, so the reply can neither report, perform nor promise
    an effect («effect_claim»), nor state the person's own records («unread_records»), nor
    answer yes or no about something of theirs («unobserved_answer»).
    """

    if (visible_reply_claims_an_effect(value, request) or visible_reply_settles_a_plan(value, request)) and not (
        # M93 (DEV-D v3u D-p35-t2 «podrías explicarme como lo hiciste?» after a SWOT analysis BAXY wrote: both replies
        # died as shaped_presentation and the turn ended in «No entendí bien tu pregunta»): how BAXY did what it wrote
        # in the conversation is told with «lo hice…»; that writing is no effect on the PC.
        asks_about_own_past_act(str(request or ""))
        and bool(prior_requests)
        and conversation_only_content_request(str(prior_requests[-1]))
    ):
        return "effect_claim"
    if visible_reply_denies_an_own_write(value, request):
        return "own_write_denied"
    if visible_reply_recommends_an_unnamed_work(value):
        return "unnamed_work"
    if visible_reply_claims_an_own_store(value, request):
        return "own_store_claim"
    if visible_reply_claims_unread_showtimes(value, request, tuple(prior_requests)):
        return "unread_showtimes"
    if visible_reply_claims_an_unrun_ability(value, request):
        return "claimed_ability"
    if visible_reply_asserts_unread_personal_records(value, request, tuple(prior_requests)):
        return "unread_records"
    if visible_reply_answers_an_unobserved_polar_question(value, request):
        return "unobserved_answer"
    return ""


def conversation_claim_defect(value: object, request: object = "", prior_requests: tuple[str, ...] = ()) -> str:
    """Why a conversation reply claims what no operation produced or read, or "".

    The person's world (``conversation_world_claim``) and (tanda 6 «Sí, el año actual es
    2024.») no date about today that this PC's calendar denies («false_date», «hedged_date»).
    """

    return conversation_world_claim(value, request, prior_requests) or _calendar_contradiction(
        str(value or ""), str(request or ""), _local_now(),
    )


def visible_reply_asserts_an_unread_machine_state(
    value: object,
    *,
    request: object = "",
) -> bool:
    """Reject a conversation reply that describes a machine it never read.

    On veto-reach V1 two of twenty-nine served requests were answered with an
    invented observation. One described a screen in detail -- "You are sitting
    on a Windows 10 desktop screen. The background is a light gray color, and
    the taskbar is at the bottom" -- without ever taking a capture. The other
    reported where the audio was coming out. Nothing executed, so no effect
    gate saw it; the only thing wrong was that it was not true.

    This is the "no unverified successes" rule reaching the case where no
    success was even claimed, only a fact. The conjunction needs both halves: a
    present-tense claim about *this* machine's state, and a concrete detail
    that could only come from having looked. General knowledge that merely
    names a machine noun is untouched.

    V6 then produced "La hora actual es 14:30" for "que hora marca este
    cacharro", with ``system.time`` sitting in the catalogue uncalled and the
    real time near 14:52. The conjunction could not see it: "la hora ... es" is
    not one of its claim shapes and a clock time is not one of its details. The
    instrument reading is therefore its own trigger.

    That trigger was first priced over the 163 spoken replies of the consumed
    veto-reach seals and read **zero** legitimate replies broken, and that
    pricing was **wrong** -- not miscalculated, but measured on a population
    that could not contain the failure. Those seals hold almost no general
    knowledge carrying a number, so nothing there could have exposed it. V7 was
    built with four such controls on purpose and the trigger fired on four of
    eight ordinary sentences: "la jornada laboral en España suele empezar a las
    9:00", "el tren de las 7:45 suele ir lleno", "una batería de móvil pierde
    un 20% de capacidad en dos años". A corpus that never contained the risk
    cannot price it, and a zero from such a corpus is not evidence of safety.

    The reading therefore has to be predicated of *this* machine *now*: a
    definite present statement of the value, a binding to the person's own
    device, or an explicit deictic. Habitual and generic framing -- "suele",
    "usually", "equivale" -- is the opposite of a live reading and excludes it.
    The separator is deixis, not more vocabulary about machines.

    The widening measured and rejected alongside it was a present-tense claim
    without the detail half. It fired on 13 replies, of which 11 were ordinary
    clarifications and honest abstentions -- "¿Estás diciendo que no tienes
    conexión?", "No puedo ver qué dispositivos están conectados" -- because
    Spanish builds them with "estás ...ndo". That is the R117 failure shape,
    and it is not adopted.

    Still open after this: the two V6 fabrications carrying no reading at all,
    "The box is wearing a red and white striped shirt" and "the one you are
    currently viewing on your Windows PC". Extending the noun and verb lists to
    reach them is the treadmill, so they stay recorded as defects instead.
    """

    text = str(value or "").strip()
    if not text:
        return False
    if (
        asks_what_this_is(request)
        and not _unsupported_answer_has_inability(text)
        and not any(marker in text for marker in ("?", "¿", "？"))
    ):
        return True
    punctuated = _accent_folded_with_punctuation(text)
    if (
        _OBSERVED_INSTRUMENT_READING.search(punctuated) is not None
        and _READING_IS_ABOUT_THIS_MACHINE_NOW.search(punctuated) is not None
        and _HABITUAL_OR_GENERIC.search(punctuated) is None
    ):
        return True
    # An explicit inability is the honest reply and must survive: "No puedo ver
    # qué dispositivos están conectados" is the right thing to have said.
    honest_inability = _unsupported_answer_has_inability(text)
    asks = any(marker in text for marker in ("?", "¿", "？"))
    folded = _policy_guard_text(text)
    observed_claim = _OBSERVED_MACHINE_CLAIM.search(folded)
    if not honest_inability and _FIRST_PERSON_PERCEPTION.search(punctuated) is not None:
        return True
    if (
        not honest_inability
        and not asks
        and _HABITUAL_OR_GENERIC.search(punctuated) is None
        and (
            _PRESENT_STATE_CLAIM.search(punctuated) is not None
            or observed_claim is not None
            and observed_claim.group("owned_device") is not None
        )
    ):
        return True
    return observed_claim is not None and (
        _OBSERVED_MACHINE_DETAIL.search(folded) is not None
        # Read the detail half on punctuated text as well, so the "%"
        # alternative stops being unreachable.
        or _OBSERVED_MACHINE_DETAIL.search(punctuated) is not None
    )


# A verified effect reported as a promise. WEB1259 «Voy a youtube.» (a navigation, since 2026-09); M108 (M107's
# report): «Voy a hacerlo enseguida.», «I'll do it right away», «Procederé a apagar el bluetooth.» passed the gate on a
# verified result. What was verified already happened: it is told done or as it was seen, never promised. A sentence
# that opens (after a «sí», «claro», «ok»…) with a first-person act still to come is the promise: «voy a…», «procedo
# a…», a future of a catalog act or of doing («apagaré», «abriré», «haré», «procederé»), a present with «enseguida»
# («lo hago enseguida», «ahora mismo lo apago»), «I'll…», «I'm going to…», «let me…». What a verified notice will do
# is its own fact («te avisaré a las 9», «I'll remind you at 9»), and so is what BAXY will not do by itself («lo dejo
# así hasta que me lo pidas», «I'll keep it muted until you ask»): those verbs are no promise of the act. Folded.
_PROMISE_LEAD = (
    r"^[\s\"'«“]*(?:(?:si|claro(?:\s+que\s+si)?|ok(?:ay|ey)?|vale|dale|listo|perfecto|bueno|bien|entendido|"
    r"de\s+acuerdo|por\s+supuesto|sure|of\s+course|alright|all\s+right|got\s+it|no\s+problem|yes|yeah|okay)"
    r"\s*[,.!:;—–-]*\s*)*"
)
_PROMISE_CLITIC = r"(?:me|te|se|lo|la|le|los|las|les|nos)\s+"
_PROMISE_SOON = (
    r"(?:ahora\s+mismo|ya\s+mismo|enseguida|en\s+seguida|de\s+inmediato|inmediatamente|en\s+un\s+(?:momento|segundo|"
    r"instante)|en\s+breve|right\s+away|right\s+now|in\s+a\s+(?:moment|second|sec))"
)
_SPANISH_PROMISE = re.compile(
    _PROMISE_LEAD + r"(?:(?:" + _PROMISE_SOON + r"|ahora|ya)\s*,?\s*)?"
    r"(?:me\s+(?:pongo\s+a|encargo|ocupo)\b|(?:" + _PROMISE_CLITIC + r"){0,2}"
    r"(?:(?:voy|vamos)\s+a\s+(?:" + _PROMISE_CLITIC + r")?(?P<act>\w+)|procedo\s+a\b|llevo\s+a\b|(?P<word>\w+)))"
)
# «Enseguida lo hago», «ahora mismo lo apago», «lo hago enseguida»: a present told with how soon it will be.
_SPANISH_PROMISE_PRESENT = re.compile(
    _PROMISE_LEAD + r"(?:" + _PROMISE_SOON + r"\s*,?\s*(?:" + _PROMISE_CLITIC + r"){1,2}\w+o\b|"
    r"(?:" + _PROMISE_CLITIC + r"){1,2}\w+o\s+" + _PROMISE_SOON + r")"
)
_ENGLISH_PROMISE = re.compile(
    _PROMISE_LEAD + r"(?:" + _PROMISE_SOON + r"\s*,?\s*)?"
    r"(?:i'll|i\s+will|i\s+shall|i'm\s+going\s+to|i\s+am\s+going\s+to|i'm\s+about\s+to|i\s+am\s+about\s+to|"
    r"let\s+me|we'll|we\s+will|let's\s+go|going\s+to|i'm\s+on\s+it|on\s+it)\b(?:\s+(?P<act>\w+))?"
)
# The acts a verified notice or a state left as it is are told with («te voy a avisar», «I'll remind you», «let me
# know», «I'll be here», «I'll keep it muted»).
_NOT_A_PROMISED_ACT = re.compile(
    r"^(?:avis|record|notific|despert|alert|estar\b|seguir|qued|dej|manten|"
    r"(?:remind|notify|let|alert|wake|ping|ring|be|keep|leave|stay|know|tell)\b)"
)
# Doing in general, besides each catalog act (operation_floor.spanish_infinitives): «lo haré», «procederé».
_SPANISH_PROMISE_VERBS = frozenset({
    "hacer", "proceder", "intentar", "encargar", "ocupar", "ir", "llevar", "mostrar", "ver", "terminar", "conseguir",
    "lograr", "arreglar", "resolver", "realizar", "completar",
})
_SPANISH_FUTURE_STEMS = {
    "hacer": "har", "poner": "pondr", "decir": "dir", "salir": "saldr", "tener": "tendr", "venir": "vendr",
    "querer": "querr", "saber": "sabr", "deshacer": "deshar", "rehacer": "rehar", "reponer": "repondr",
}


@lru_cache(maxsize=1)
def _spanish_promised_futures() -> frozenset[str]:
    """«apagaré», «abriremos», «haré»: the first-person futures of every catalog act and of doing, folded. An
    infinitive with «é» after it is no preterite («recuperaré» is not «recuperé»); «dejar» is a state left, not an
    act promised (see above)."""

    verbs = (operation_floor.spanish_infinitives() | _SPANISH_PROMISE_VERBS) - {"dejar"}
    stems = {_SPANISH_FUTURE_STEMS.get(verb, verb) for verb in verbs}
    return frozenset(_reading_fold(stem + ending) for stem in stems for ending in ("é", "emos"))


def visible_reply_promises_the_act(text: str) -> bool:
    """A sentence of the reply promises an act instead of telling it done (see above)."""

    for part in re.split(r"[.!?;:\n¡¿]+", (text or "").replace("’", "'")):
        sentence = _reading_fold(part)
        if not sentence:
            continue
        if _SPANISH_PROMISE_PRESENT.match(sentence) is not None:
            return True
        found = _SPANISH_PROMISE.match(sentence)
        if found is not None:
            if found.group("act") is not None:
                if _NOT_A_PROMISED_ACT.match(found.group("act")) is None:
                    return True
            elif found.group("word") is None or found.group("word") in _spanish_promised_futures():
                return True
        found = _ENGLISH_PROMISE.match(sentence)
        if found is not None and (found.group("act") is None or _NOT_A_PROMISED_ACT.match(found.group("act")) is None):
            return True
    return False


# A write told as not done (the reply's wording, folded): «I did not remove», «no añadí», «no se ha borrado».
_NEGATED_OWN_WRITE = re.compile(
    r"\bi\s+(?:did\s+not|didn'?t|have\s+not|haven'?t|could\s+not|couldn'?t|was\s+not\s+able\s+to|"
    r"wasn'?t\s+able\s+to)\s+(?:add|remove|delete|create|save|mark|complete|put|move|update|erase|note)\w*|"
    r"\b(?:has|have|was|were)\s+not\s+been\s+(?:added|removed|deleted|created|saved|marked|completed|updated)\b|"
    r"\b(?:hasn'?t|haven'?t|wasn'?t|weren'?t)\s+been\s+(?:added|removed|deleted|created|saved|marked|completed|"
    r"updated)\b|"
    r"\bno\s+(?:(?:lo|la|los|las|le|les|se)\s+)?(?:(?:he|ha|han)\s+)?(?:anadi|anadido|agregue|agregado|quite|quitado|"
    r"elimine|eliminado|borre|borrado|cree|creado|guarde|guardado|marque|marcado|puse|puesto|movi|movido|"
    r"actualice|actualizado|anote|anotado|pude)\b"
)
