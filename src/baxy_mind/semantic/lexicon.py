"""The words of each domain, said once.

A family's nouns and verbs used to be written again in every place that read them — the pattern reader, the
domain-grounding gate, the argument binder and the composer's vetoes — and each copy drifted: the owner's
«poné en mute el micro» (held-out 2026-09-22) was read by one copy («micro» known) and vetoed by another
(«micro» unknown), so BAXY asked instead of acting. Every reader of a family now imports its words from here;
a new synonym is added once and every stage agrees.

Words are folded (see ``normalize.fold``). Where a list was inherited, the comment says from where.
"""

from __future__ import annotations

from .normalize import alternation

# ---------------------------------------------------------------- microphone (audio.microphone.mute)
# Seeded from planner._MICROPHONE_* (owner's test 2026-09-21, turn 205), the most complete copy.
MICROPHONE_NOUNS = frozenset({"microfono", "microfonos", "microphone", "microphones", "mic", "mics", "micro"})
# The microphone's boolean is «muted»: these words ask for muted = true.
MICROPHONE_MUTE_WORDS = frozenset(
    {
        "mute", "mutea", "muteame", "mutealo", "mutear", "muteen", "silencia", "silenciame", "silencialo",
        "silenciar", "silence", "apaga", "apagame", "apagalo", "apagar", "desactiva", "desactivame",
        "desactivalo", "desactivar", "calla", "callalo", "deshabilita", "disable", "off",
    }
)
# ... and these ask for muted = false.
MICROPHONE_UNMUTE_WORDS = frozenset(
    {
        "activa", "activame", "activalo", "activar", "activate", "reactiva", "reactivalo", "reactivar",
        "reactivate", "enciende", "enciendelo", "encende", "encendelo", "prende", "prendeme", "prendelo",
        "prender", "habilita", "habilitalo", "enable", "desmutea", "desmutealo", "desmutear", "unmute",
        "desilencia", "dessilencia", "on",
    }
)
MICROPHONE_NOUN = alternation(MICROPHONE_NOUNS)
MICROPHONE_VERB = alternation((MICROPHONE_MUTE_WORDS | MICROPHONE_UNMUTE_WORDS) - {"on", "off"})
# «poné en mute el micro», «ponle mute»: the state said as a noun after a light verb.
MUTE_PHRASE = r"(?:pon(?:e|le|ele)?|poner|dale|deja|dejar)\s+(?:en\s+)?mute"

# ---------------------------------------------------------------- settings of this PC
# What «bajar/subir/poner» adjusts rather than downloads (effect_intent._VOLUME_OBJECT, the brightness readers).
VOLUME_NOUNS = frozenset({"volumen", "volume", "sonido", "sound", "audio"})
BRIGHTNESS_NOUNS = frozenset({"brillo", "brightness"})
SETTING_NOUNS = VOLUME_NOUNS | BRIGHTNESS_NOUNS | MICROPHONE_NOUNS
SETTING_NOUN = alternation(SETTING_NOUNS)
# The PC's loudspeaker, as each region names it. Tanda 2 «Silenciar la bocina please»: «bocina» is the speaker in
# Mexico and Central America; it was asked about instead of muted.
SPEAKER_NOUNS = frozenset(
    {"altavoz", "altavoces", "parlante", "parlantes", "bocina", "bocinas", "speaker", "speakers"}
)
SPEAKER_NOUN = alternation(SPEAKER_NOUNS)

# ---------------------------------------------------------------- restoring the system sound (audio.mute, muted = false)
# Held-out 2026-09-22 «devolvele el sonido»: giving the sound back is unmuting it.
# Each verb with the clitics people fuse to it («devolveme», «devuélvenos», «restaurale»), generated once.
_AUDIO_RESTORE_VERBS = ("devuelve", "devolve", "devolver", "restaura", "restaurar", "recupera", "recuperar")
AUDIO_RESTORE_WORDS = frozenset(
    {verb + clitic for verb in _AUDIO_RESTORE_VERBS for clitic in ("", "me", "le", "les", "nos", "lo")}
)
AUDIO_RESTORE = alternation(AUDIO_RESTORE_WORDS)
# Uso real 2026-09-23 «vuelve el sonido»: the sound coming back, with the sound as its subject. «vuelve» and
# «regresa» say nothing about the sound on their own («vuelve a abrir Spotify»), so they are not restore words
# (which the planner also reads as «off» cues). They count only together with the sound.
# Tanda 6 «Quiero el sound de nuevo please» was answered as a limit: the sound wanted, asked for or given back
# again («quiero el sonido de nuevo», «dame el audio otra vez», «I want my sound back», «bring back the sound»,
# «quiero de vuelta el sonido») is the sound coming back too. The «again» word is what says it: «quiero el sonido
# más alto» is a level, and «el sonido de las notificaciones» another sound.
_SOUND_WANTED = (
    r"(?:quiero|quisiera|necesito|dame|damelo|devuelveme|give\s+me|i\s+(?:want|need)|i'?d\s+like|"
    r"(?:can|could)\s+i\s+(?:have|get)|bring|get)"
)
_SOUND_WORD = r"(?:(?:el|la|the|mi|my)\s+)?(?:sonido|audio|sound)"
_AGAIN = r"(?:de\s+nuevo|otra\s+vez|de\s+vuelta|back(?:\s+on)?|again)"
SOUND_BACK = (
    rf"(?:(?:{AUDIO_RESTORE}|vuelve|volve|vuelva|regresa|regrese)\s+{_SOUND_WORD}|"
    rf"{_SOUND_WANTED}\s+(?:{_SOUND_WORD}\s+{_AGAIN}|(?:de\s+vuelta|back)\s+{_SOUND_WORD})"
    r"(?=\s*(?:[,.;:!?]|$|\s(?:por\s+favor|porfa|please|ya|ahora|now)\b)))"
)

# ---------------------------------------------------------------- the mute as a switch (audio.mute)
# Uso real 2026-09-23 «Turn off silenciar»: the mute said as a thing that is switched off (muted = false) or on
# (muted = true), in Spanish, English or both. «quitá el silencio» was read before; the other switches were not.
_MUTE_STATE_NOUN = r"(?:(?:el|la|the)\s+)?(?:modo\s+)?(?:mute|silencio|silenciar|mudo|silence|silent(?:\s+mode)?)"
MUTE_SWITCH_OFF = (
    r"(?:turn(?:ed)?\s+off|switch\s+off|apaga(?:r|le)?|desactiva(?:r|le)?|disable|deactivate|"
    r"quita(?:r|le)?|saca(?:r|le)?|remove)\s+" + _MUTE_STATE_NOUN
)
# MASSIVE audio_volume_mute (dev corpus 2026-09-24) «set mute until said otherwise»: the mute set, like switched on.
MUTE_SWITCH_ON = (
    r"(?:turn\s+on|switch\s+on|activa(?:r|le)?|enciende|prende|enable|set(?:\s+(?:it\s+)?(?:to|on))?)\s+"
    + _MUTE_STATE_NOUN
)
# Tanda 4 2026-09-24 «Enciende el sound» was answered as a limit: the sound itself switched on is the mute
# switched off (muted = false), and the sound switched off is the mute on (muted = true), in Spanish, English or
# both. Only the sound, the audio or the PC's own sound is the object: «enciende la música» plays, «apaga el PC»
# shuts down, «prende los parlantes» may be a Bluetooth device.
# Tanda 5: «apaga el volumen» is the sound switched off too.
_SOUND_NOUN = r"(?:(?:el|la|los|the|mi|my)\s+)?(?:sonido|sonidos|sound|sounds|audio|volumen|volume)(?:\s+(?:del?|of)\s+(?:(?:el|la|the|mi|my)\s+)?(?:pc|equipo|computador(?:a)?|computer|sistema|system))?"
_SOUND_ON_VERB = (
    r"(?:turn(?:ed)?\s+on|switch\s+on|enable|activa(?:r|le)?|enciende(?:le)?|encende(?:le)?|encender|prende(?:le)?|"
    r"prender|habilita(?:r)?)"
)
_SOUND_OFF_VERB = r"(?:turn(?:ed)?\s+off|switch\s+off|disable|apaga(?:r|le)?|desactiva(?:r|le)?|deshabilita(?:r)?)"
# The sound ends the order: «desactiva el sonido de las notificaciones» is another sound.
_SOUND_ORDER_END = (
    r"(?=\s*(?:[,.;:!?]|$|\s(?:y|and|por\s+favor|porfa|please|ya|ahora|now|de\s+nuevo|again|otra\s+vez)\b))"
)
# MASSIVE audio_volume_up (dev corpus 2026-09-24) «audio on»: the switch said as its state, with no verb, when the
# message opens with the sound.
SOUND_SWITCH_ON = (
    rf"(?:{_SOUND_ON_VERB}\s+{_SOUND_NOUN}|turn\s+{_SOUND_NOUN}\s+on|^[¿¡\s]*{_SOUND_NOUN}\s+on){_SOUND_ORDER_END}"
)
SOUND_SWITCH_OFF = (
    rf"(?:{_SOUND_OFF_VERB}\s+{_SOUND_NOUN}|turn\s+{_SOUND_NOUN}\s+off|^[¿¡\s]*{_SOUND_NOUN}\s+off){_SOUND_ORDER_END}"
)

# Uso real 2026-09-23 «silencio»: the bare silence order, the whole message. MASSIVE audio_volume_mute (dev corpus
# 2026-09-23) «silencio altavoces», «altavoces en silencio»: the silence with the speakers or the sound it falls on,
# still with no verb.
_SILENCED_OBJECT = rf"(?:(?:los|las|el|la|the|mis|my)\s+)?(?:{SPEAKER_NOUN}|sonidos?|sounds?|audio)"
# M97 (reserve, MASSIVE audio_volume_mute): a silence order whose only complement is a span of time («silencia por
# dos horas», «quédate callado un rato», «be quiet for another hour», «mudo por una hora») is the mute too, said to
# the PC. BAXY has no timer that gives the sound back; the reply says so (the owner's rule for a timed mute). «Cállate»
# with no span is not here: said alone to BAXY it may be about his voice.
_SPAN_OF_TIME = (
    r"(?:(?:por|durante|for|during)\s+)?"
    r"(?:(?:otr[oa]s?|un[oa]?|unos|unas|medi[oa]|an?|another|the\s+next|next|(?:los|las)\s+proxim[oa]s|par\s+de|"
    r"couple\s+of|few|\d+|dos|tres|cuatro|cinco|diez|quince|veinte|treinta|two|three|four|five|ten|fifteen|twenty|"
    r"thirty)\s+)*"
    r"(?:horas?|minutos?|mins?|ratos?|ratito|segundos?|hours?|minutes?|while|bit)"
)
_SILENCE_ORDER = (
    r"(?:silencia(?:lo|la|me)?|silenciar|mutea(?:lo|me)?|mutear|mute|callate|callese|callense|"
    r"quedate\s+callad[oa]|be\s+quiet|keep\s+quiet|stay\s+quiet|quiet\s+down|shut\s+up|silence|silencio|mudo|"
    r"(?:pon(?:lo|me)?|deja(?:lo)?|put|go)\s+(?:(?:en|on|in)\s+)?(?:silencio|mudo|mute))"
)
TIMED_SILENCE = (
    rf"(?:(?:por\s+favor|porfa|please)\s*,?\s+)?{_SILENCE_ORDER}"
    r"(?:\s+(?:todo|everything|it|el\s+sonido|el\s+audio|the\s+sound|the\s+audio))?"
    rf"\s+{_SPAN_OF_TIME}(?:\s+(?:mas|more))?(?:\s*,?\s+(?:por\s+favor|porfa|please))?"
)
BARE_SILENCE = (
    r"^[¿?¡!\s]*(?:"
    rf"(?:silencio|mudo|silence|quiet)(?:\s+(?:(?:en|a|on|for)\s+)?{_SILENCED_OBJECT})?|"
    rf"{_SILENCED_OBJECT}\s+(?:en\s+)?(?:silencio|mudo|mute)|"
    rf"{TIMED_SILENCE}"
    r")(?:\s+(?:total|por\s+favor|porfa|please|ya|ahora))?[\s.!?]*$"
)


# ---------------------------------------------------------------- stopping a noise (audio.mute, muted = true)
# Tanda 2026-09-23 «¡detén este horrible ruido!»: a stop order whose object is a noise asks for silence. It was
# answered with a question. Stopping music or a video is media.control; a noise is not something that plays.
NOISE_STOP = (
    r"(?:deten(?:er|lo)?|para(?:r|lo)?|pare|calla(?:r|lo)?|stop|kill|corta(?:r|lo)?|quita(?:r|lo)?|apaga(?:r|lo)?|"
    r"shut\s+(?:off|up))\s+(?:(?:este|ese|esta|esa|el|la|los|that|this|the)\s+)?(?:[a-z]+\s+)?"
    r"(?:ruido|ruidos|noise|bulla|barullo|escandalo|racket)"
)

# A message that opens with one of the above is a mute request by its form (the verbs alone, «vuelve», «para»,
# «apaga», head many other requests).
MUTE_REQUEST = (
    rf"^[¿?¡!\s]*(?:{SOUND_BACK}|{MUTE_SWITCH_OFF}|{MUTE_SWITCH_ON}|{SOUND_SWITCH_ON}|{SOUND_SWITCH_OFF}|{NOISE_STOP})\b"
    rf"|{BARE_SILENCE}"
)
# What asks for muted = false, and muted = true, in every reader and the argument binder.
UNMUTE_WORDS = rf"{SOUND_BACK}|{MUTE_SWITCH_OFF}|{SOUND_SWITCH_ON}"
MUTE_WORDS = rf"{MUTE_SWITCH_ON}|{SOUND_SWITCH_OFF}|{NOISE_STOP}"

# ---------------------------------------------------------------- people of the person's own life
# Tanda 3 2026-09-24 «es cierto que el cumpleaños de antonia es el primero de marzo» was searched on the web: someone
# named only by a given name is someone the person knows, and what is asked of them is the person's own data
# (web.names_own_data). The most common given names in Spanish and English, their usual short forms («paco», «alex»),
# and a few of the most common Indian ones English speakers use (dev corpus 2026-09-23 «call raju phone number»,
# messaging.contact_book_request). Left out on purpose: names that are also
# common words, months, places, holidays, brands, cartoon pairs or a famous single-name artist («rosa», «luz», «julio»,
# «june», «victoria», «santiago», «mercedes», «mario», «tom», «camilo»), where a bare mention is not a private person.
GIVEN_NAMES = frozenset(
    """
    juan jose luis carlos jorge pedro pablo miguel manuel antonio francisco javier fernando rafael ricardo roberto
    sergio alejandro andres diego daniel david alberto eduardo enrique felipe gabriel gonzalo hector ignacio jaime
    joaquin lucas martin mateo matias nicolas raul rodrigo ruben samuel sebastian vicente agustin benjamin bruno
    cristian emilio esteban facundo gustavo ivan julian maximiliano mauricio patricio ramiro thiago victor alvaro
    adrian emiliano gerardo alonso arturo elias ernesto fabian federico guillermo hernan leandro lorenzo marcelo
    octavio renato rodolfo ulises walter ramon benito cristobal felix alfredo bastian nahuel lautaro santino
    maria ana laura carmen isabel lucia martina valentina camila antonia paula andrea daniela gabriela fernanda
    catalina josefa javiera constanza francisca isidora agustina emilia julieta juana marta elena cristina patricia
    monica veronica claudia silvia beatriz raquel sara sandra natalia adriana alejandra alicia diana eva irene ines
    lorena mariana miriam nuria olga susana teresa ximena jimena valeria yolanda zoe fabiola graciela josefina
    liliana maite micaela noelia pamela paola renata romina tamara vanesa viviana luciana antonella bianca agostina
    amanda barbara estefania gisela karina karla marisol nicole priscila rebeca tatiana almudena lola
    alex paco pepe lucho chema manolo rafa dani santi nico fede beto lalo toni andy
    raju rahul priya amit ravi arjun neha pooja
    john james robert michael william richard joseph thomas charles christopher matthew anthony steven paul andrew
    joshua kenneth kevin brian george edward ronald timothy jason jeffrey ryan jacob gary nicholas eric jonathan
    stephen larry justin scott brandon gregory alexander patrick dennis tyler aaron adam nathan henry zachary
    douglas peter kyle noah ethan jeremy keith roger terry sean gerald carl harold dylan lawrence jesse bryan billy
    bruce joe logan alan ralph randy eugene vincent russell bobby philip johnny liam oliver owen caleb isaac
    nathaniel tony steve mike chris matt dave rick tim jim sam dan luke
    mary jennifer elizabeth susan jessica sarah karen lisa nancy betty margaret ashley kimberly emily donna michelle
    melissa deborah stephanie dorothy rebecca sharon cynthia amy kathleen angela shirley brenda emma anna samantha
    katherine christine helen debra rachel carolyn janet catherine heather olivia julie joyce ruth lauren christina
    joan evelyn judith hannah megan cheryl jacqueline martha janice ann kathryn abigail sophia frances alice judy
    isabella julia denise danielle marilyn beverly natalie theresa brittany doris kayla alexis lori marie chloe mia
    ava ella ellie jessie
    """.split()
)

# ---------------------------------------------------------------- social networks
# The networks a person posts to or has an account on (messaging.social_network_request); what happens «in my social
# media» is their account, never the news of a place (web.news_lookup_query).
SOCIAL_NETWORK = (
    r"(?:facebook|instagram|twitter|tiktok|linkedin|threads|mastodon|bluesky|tumblr|snapchat|pinterest|"
    r"redes?\s+sociales?|social\s+(?:media|networks?))"
)

# ---------------------------------------------------------------- the canonical surface (semantic.surface)
# Tanda 3 (2026-09-24): words people use for something BAXY serves that no reader knows by that word. Each maps to
# the word the readers read; ``semantic.surface`` rewrites them before a limit is published.
# «hacer sonar» is «poner» (each form of «hacer» to the same form of «poner»).
MAKE_SOUND_FORMS = {
    "haz": "pon", "hazme": "ponme", "hace": "pone", "haceme": "poneme", "hacer": "poner", "hacerme": "ponerme",
    "hagas": "pongas", "haga": "ponga", "hagan": "pongan", "hagamos": "pongamos",
}
# What rings rather than plays: «haz sonar el timbre» is not «pon el timbre».
RINGING_THINGS = frozenset(
    {"timbre", "campana", "campanas", "sirena", "claxon", "bocina", "celular", "telefono", "movil", "phone"}
)
# «inactivar» is «desactivar», in every form.
INACTIVE_STEM = "inactiv"
# What people call the pictures folder of this PC.
GALLERY_NOUNS = frozenset({"gallery", "galeria", "galerias"})
# A desire said before «que» + the order in the subjunctive: «me apetece que pongas…», «quiero que me abras…».
DESIRE_FRAMES = frozenset(
    {
        "quiero", "quisiera", "queria", "necesito", "me gustaria", "me encantaria", "me apetece", "me provoca",
        "se me antoja", "tengo ganas de", "te pido",
    }
)
# The tú subjunctive whose imperative the ending rules below do not give.
IRREGULAR_IMPERATIVES = {
    "pongas": "pon", "hagas": "haz", "digas": "di", "vayas": "ve", "tengas": "ten", "salgas": "sal",
    "vengas": "ven", "sigas": "sigue", "detengas": "deten", "leas": "lee", "veas": "ve", "elijas": "elige",
}
# The list itself as what is added: «añadir una nueva lista» creates the list.
LIST_ADD_VERBS = frozenset({"anade", "anadir", "anademe", "agrega", "agregar", "agregame", "add"})

# ---------------------------------------------------------------- the person's address before a request
# Tanda t4-r6 «bro abre excel y crea un libro en blanco» lost its place (Excel) while «abre excel y …» kept it: a
# vocative or a discourse marker said before an order is only how the person speaks to BAXY, never part of the order.
# Spoken without a comma; the order after it must still start with an action (``grammar._strip_request_envelope``),
# so «bro» inside a file name or quoted text, or a marker before no order («oye, qué hora es»), stays as said.
# English «pal» is left out: in Spanish speech «pal» is «para el» («pal lunes recuérdame…»), never the address.
ADDRESS_VOCATIVES = frozenset(
    {
        "bro", "brother", "hermano", "hermana", "mano", "manito", "wey", "guey", "compa", "compadre", "amigo",
        "amiga", "socio", "loco", "viejo", "weon", "hueon", "dude", "buddy", "mate", "che", "oye", "oiga",
        "hey", "ey", "mira", "escucha", "bueno", "vale",
    }
)
ADDRESS_VOCATIVE = alternation(ADDRESS_VOCATIVES)
# «vale», «ok», «bueno»: the word that takes the answer before in, said before the order and no part of it.
ACKNOWLEDGEMENTS = frozenset({"ok", "okay", "vale", "bueno", "dale", "listo"})
# r31: every word that only links an order to the talk before it. A run of them is dropped only before a head the
# reader anchors on (a window order): before free text «right click…» or «bien hecho» keep theirs.
SPOKEN_LINKS = ACKNOWLEDGEMENTS | ADDRESS_VOCATIVES | {
    "ya", "okey", "bien", "perfecto", "ahora", "luego", "despues", "entonces", "tambien", "y", "pues", "baxy", "now",
    "alright", "right", "then", "also", "so", "and", "por favor", "porfa", "please",
}
SPOKEN_LINK = alternation(SPOKEN_LINKS)
# The view of the bare pronoun («ya, ciérrala»), as M96 measured it: «después lo cierras» is not «ciérralo» now.
POINTER_LINK = alternation(
    SPOKEN_LINKS - {"luego", "despues", "tambien", "also"} - (ADDRESS_VOCATIVES - {"oye", "che", "hey", "bueno", "vale"})
)
# r31: how a clause that only tells why opens — the one list. Each reader ends at a declared view of it, the openers
# it always read, so none gains a word nobody measured. «que» alone also says which one and is none.
REASON_OPENERS = frozenset({
    "porque", "porq", "pq", "xq", "pues", "ya que", "puesto que", "dado que", "que me", "que nos", "que te",
    "que ya no", "because", "since", "cause", "cuz", "cos", "as it", "as i", "q me", "q nos", "q te", "k me", "k nos",
    "k te", "so i", "para que", "pa que",
})
_CHAT_QUE = {"q me", "q nos", "q te", "k me", "k nos", "k te"}
REASONS_SAID_BACK = REASON_OPENERS - _CHAT_QUE - {"so i", "para que", "pa que"}  # ronda 24, as measured
# A window order ends in none that a name also holds («just cause», «dead since dawn», «as it is»).
REASONS_OF_A_WINDOW_ORDER = REASON_OPENERS - {"cause", "since", "cos", "as it", "as i", "para que", "pa que"}
REASONS_AFTER_A_TITLE = REASON_OPENERS - REASON_OPENERS.intersection(
    {"pues", "puesto que", "dado que", "que ya no", "cuz", "cos", "as it", "as i", "so i"}
)
REASONS_AFTER_A_PLACING = REASON_OPENERS & {"porque", "because"}


def reason_opening(openers: frozenset[str]) -> str:
    """The regex of one view of ``REASON_OPENERS``, the longest opener first."""

    said = sorted(openers, key=lambda opener: (-len(opener), opener))
    return "(?:" + "|".join(opener.replace(" ", r"\s+") for opener in said) + r")\b"

# ---------------------------------------------------------------- a new document of an application (app.open)
# Uso real t4-r6 c14 «pegame lo que copie en un bloc de notas nuevo» pasted into the person's open note, and c06
# «crea un blank workbook» with Excel open made nothing: «nuevo» was lost and app.open reused the window there. These
# words said next to what is opened (a document noun or the application's own name) ask for a new document.
NEW_DOCUMENT_MARKERS = frozenset({"nuevo", "nueva", "new", "blank", "vacio", "vacia", "empty"})
# Said after the document only: «un excel en blanco».
NEW_DOCUMENT_AFTER_PHRASES = frozenset({("en", "blanco")})
# Said before the document only, a determiner of their own: «otro documento», «another document».
NEW_DOCUMENT_BEFORE_ONLY = frozenset({"otro", "otra", "another"})
# «de nuevo» is «again», never a new document («abre de nuevo el bloc de notas»).
NEW_DOCUMENT_AGAIN_LEAD = frozenset({"de"})
# The grammar words next to a marker, never the application's name («lo nuevo de bad bunny»: the catalog reader
# matches a bare «de» to «Bloc de notas»).
NEW_DOCUMENT_GRAMMAR_WORDS = frozenset(
    {
        "de", "del", "el", "la", "lo", "los", "las", "un", "una", "en", "y", "a", "al", "con", "por", "para", "the",
        "of", "in", "and", "an", "with", "to", "for",
    }
)
# Review of cu-v3-documento-nuevo (finding 3): the word that leads the document says whose it is. «un/una/a/an» (or
# «otro/otra/another», above) asks for one that does not exist yet; an article or a possessive points at one there
# («abre el documento nuevo que hice ayer», «abre mi nota nueva», «abre el nuevo outlook»: the product's name).
NEW_DOCUMENT_INDEFINITE = frozenset({"un", "una", "a", "an"})
NEW_DOCUMENT_THEIRS = frozenset(
    {
        "el", "la", "los", "las", "lo", "mi", "mis", "tu", "tus", "su", "sus", "este", "esta", "ese", "esa", "aquel",
        "aquella", "the", "my", "your", "his", "her", "our", "their", "this", "that",
    }
)
# With no leading word only a marker no product's name carries asks for it («abre excel en blanco»); «abre teams
# nuevo» and «escribe nota nueva de compras» ask for none.
NEW_DOCUMENT_PLAIN_MARKERS = frozenset({"blank", "vacio", "vacia", "empty", "en blanco"})
# The words that tie a document to the application it is made in: «un documento nuevo de word», «in word».
NEW_DOCUMENT_OF = frozenset({"de", "del", "en", "in", "on", "of"})
# An application said after these is where something comes from, never where a document is made: «copia el título
# de la página de chrome y pegalo en un documento nuevo» asks Chrome for no new document.
NEW_DOCUMENT_SOURCE_LEAD = frozenset({"de", "del", "desde", "from", "of"})
# What a document application opens, said by its kind. A window is no document: «abre spotify en otra ventana» asks
# for no New command (in a player it makes a playlist in the person's account).
DOCUMENT_NOUNS = frozenset(
    {
        "documento", "archivo", "nota", "notas", "libro", "hoja", "planilla", "presentacion", "doc", "document",
        "file", "note", "notes", "workbook", "sheet", "spreadsheet", "presentation",
    }
)
# Revisión 2 de r24b (B1: «en excel agregá una hoja nueva» opened a new workbook by Ctrl+N and the person's book stayed
# without the sheet; «en el explorador de archivos crea un archivo nuevo» opened another Explorer window): the kinds
# that name a whole document an editor makes on its New command, never a part of one (a sheet, a note, a page) nor an
# item of a folder (a file). Only these make the new document over the application already in front
# (cu_documents._new_document_in_front).
WHOLE_DOCUMENT_NOUNS = frozenset({"documento", "libro", "presentacion", "doc", "document", "workbook", "presentation"})

# ---------------------------------------------------------------- an order that makes a thing (computer use)
# Pasada r15b2 (v3-35 «crea una nota rapida nueva»): the verbs whose object is a thing made, so «una nota rápida» is
# made in the application of that name (``missions.application_said_as_object``). Review of the branch: any other
# verb leaves the object as no thing made — «compra una cámara», «recomiéndame una terminal», «dime una nota rápida»,
# «ponme una música», «busca un terminal» (a web search) name no application to work in.
MAKE_VERBS = frozenset(
    {
        "crea", "crear", "creame", "crealo", "creala", "haz", "hazme", "hace", "haceme", "hacer", "hacerme",
        "genera", "generame", "generar", "arma", "armame", "armar", "agrega", "agregame", "agregar", "anade",
        "anademe", "anadi", "anadir", "escribe", "escribeme", "escribi", "escribime", "escribir", "anota", "anotame",
        "anotar", "redacta", "redactame", "redactar",
        "create", "make", "add", "write", "draft",
    }
)

# ---------------------------------------------------------------- the shape of an order for the engine (computer use)
# Uso real v3 ronda 19 (t3-c02/1 «en el excel que tengo abierto seleccioná la fila 1…»): a relative clause that only
# says the application is the one already open frames nothing more and asks nothing; the order follows it.
OPEN_APPLICATION_RELATIVES = frozenset(
    {
        "que tengo abierto", "que tengo abierta", "que tengo abiertos", "que tengo abiertas", "que tenes abierto",
        "que tenes abierta", "que tienes abierto", "que tienes abierta", "que tengo ahi abierto",
        "que tengo ahi abierta", "que tengo ya abierto", "que tengo ya abierta", "que esta abierto", "que esta abierta",
        "que ya esta abierto", "que ya esta abierta", "que deje abierto", "que deje abierta",
        "that i have open", "that i've got open", "that ive got open", "i have open", "that is open", "thats open",
        "that's open", "which is open", "that is already open",
    }
)
# Uso real v3 ronda 19 (t2-c10 «poné el titulo en negrita», t2-c11 «elige el lapiz con color azul»): what an order
# «<objeto> en/con <atributo>» applies to the object it selects is a format of the selection or a tool to choose,
# never part of the control's name. Colours are ``colours.is_basic_colour``'s.
FORMAT_ATTRIBUTES = frozenset(
    {
        "negrita", "negritas", "cursiva", "cursivas", "italica", "subrayado", "subrayada", "tachado", "tachada",
        "centrado", "centrada", "mayusculas", "versalitas", "superindice", "subindice",
        "bold", "italic", "italics", "underline", "underlined", "strikethrough", "uppercase", "all caps",
        "small caps", "superscript", "subscript",
    }
)
TOOL_ATTRIBUTES = frozenset(
    {
        "lapiz", "pincel", "borrador", "goma", "goma de borrar", "balde", "bote de pintura", "relleno", "aerografo",
        "cuentagotas", "lupa", "resaltador", "marcador",
        "pencil", "brush", "eraser", "fill", "bucket", "paint bucket", "airbrush", "eyedropper", "magnifier",
        "highlighter", "marker",
    }
)
COLOUR_NOUNS = frozenset({"color", "colour"})
# Ronda 22 (r18 t4-c18 «en paint elegí el balde de pintura y el color rojo»): the words that join two objects of one
# choice, and the nouns of a kind of choice that, said with their own article and a name after them («el color rojo»,
# «la herramienta lápiz», «the colour red»), start a second object chosen with the same verb. A name that carries
# «y» without its own article and kind («Sonido y vídeo», «Brillo y color») stays one name.
OBJECT_COORDINATORS = frozenset({"y", "e", "and"})
CHOICE_KIND_NOUNS = frozenset(
    {"color", "colour", "herramienta", "tool", "opcion", "option", "forma", "shape", "fuente", "font"}
)
# Ronda 22, revisión 2: a kind noun followed by one of these words names a part of the thing chosen («el color de
# relleno», «el color de la línea», «the colour of the line»), never a second object: its complement is no name to
# choose (the fill tool, the Line tool), and the piece stays in the one name said.
KIND_COMPLEMENT_WORDS = frozenset({"de", "del", "of", "for"})
# The verbs that put an attribute on an object («poné el título en negrita», «put the title in bold»).
SETTING_VERBS = frozenset({"pone", "pon", "ponga", "deja", "dejame", "put", "set", "make", "turn", "leave"})

# ---------------------------------------------------------------- calling off what was asked (dialogue.calls_off)
# Revisión adversarial 2 r19 («no, déjalo así», «no, cancela eso», «no, dejalo nomas», «no, déjalo como está» after an
# application was opened reached the engine as orders in it): the verbs that call off what was asked or leave things
# as they are, in the forms said to BAXY. «deja de …», «para», «stop» and «skip» are kept out: each is also an order
# of its own in an application.
CALL_OFF_VERBS = frozenset(
    {
        "deja", "deje", "dejalo", "dejala", "dejalos", "dejalas", "dejelo", "dejela", "dejemos", "dejemoslo",
        "dejemosla", "dejar", "dejarlo", "dejarla", "dejamos", "cancela", "cancele", "cancelalo", "cancelala",
        "cancelemos", "cancelemoslo", "cancelar", "cancelarlo", "anula", "anule", "anulalo", "anulala", "anular",
        "olvida", "olvide", "olvidalo", "olvidala", "olvidate", "olvidese", "olvidemos", "olvidemoslo", "olvidar",
        "olvidarlo", "descarta", "descartalo", "descartala",
        "cancel", "forget", "leave", "drop", "scrap", "abort", "nevermind",
    }
)
# Revisión adversarial 3 r19: of those verbs, the ones that said alone are also an order in an application (the
# dialog's «Cancelar» or «Descartar» button, leaving a call or a meeting). Said bare, with no lead and nothing after
# («cancelá», «leave»), they reach the engine as the base did; «no, cancelá», «cancela eso» still call off.
CALL_OFF_BARE_ORDERS = frozenset(
    {
        "cancela", "cancele", "cancelar", "anula", "anule", "anular", "descarta", "descartar",
        "cancel", "leave", "abort", "drop", "discard",
    }
)
# What may come before such a verb and still only call off («no», «mejor», «espera», «actually»).
CALL_OFF_LEADS = frozenset(
    {
        "no", "nop", "nope", "nah", "nel", "mejor", "bueno", "ok", "okay", "oh", "ya", "entonces", "pues", "espera",
        "esperate", "pera", "perdon", "sorry", "wait", "actually", "eh", "mm", "bro", "man", "che", "never", "just",
        "please", "porfa",
    }
)
# What may come after it and leave nothing to do: an object pronoun or demonstrative and how things stay
# («así», «como está», «tal cual», «nomás», «ahí», «por ahora», «en paz», «as it is», «like that», «for now»).
# Never how things were (revisión adversarial 3: «déjalo como estaba», «leave it as it was» ask to undo, the same as
# c04 T3 «regresala como estaba»): «estaba», «estaban», «was», «were» are kept out.
CALL_OFF_MODIFIERS = frozenset(
    {
        "asi", "como", "esta", "estan", "tal", "cual", "nomas", "no", "mas", "ahi", "alli", "aca",
        "aqui", "eso", "esto", "todo", "mejor", "ya", "por", "ahora", "hoy", "de", "momento", "el", "lo", "la", "en",
        "paz", "igual", "nada", "porfa", "favor", "entonces", "pues", "mismo", "sin", "cambios", "tranqui", "bro",
        "it", "its", "as", "is", "like", "that", "this", "there", "here", "alone", "for", "now", "be", "then",
        "please", "all", "everything", "about", "mind", "today", "unchanged", "the", "way",
    }
)

# ---------------------------------------------------------------- what is opened to be seen (missions._OPEN_TO_SEE)
# Revisión adversarial 2 r19 («abre la calculadora para ver cuanto es 5 por 8», «abre whatsapp para ver si me escribio
# mi mama», «open chrome to see what's new» became «ir a <cláusula>»): the words that head a clause or a question
# after «ver», «see», «check»; what follows them is something to find out, never a place of the application.
SEEN_CLAUSE_HEADS = frozenset(
    {
        "si", "que", "cuanto", "cuanta", "cuantos", "cuantas", "como", "cuando", "donde", "adonde", "cual", "cuales",
        "quien", "quienes", "porque", "lo que", "lo cual", "los que", "las que", "el que", "la que", "a ver",
        "if", "whether", "what", "whats", "how", "when", "where", "which", "who", "whos", "whose", "why", "that",
    }
)
# Revisión adversarial 3 r19 («abre youtube para ver videos de gatos», «abre word para ver el informe», «abre excel
# para ver las ventas» became «ir a <contenido>»): what is opened «para ver» is a place of the application only when
# the person says it is a part of it — «lo de la pantalla», «la sección de cuentas», «the part about privacy». Bare,
# what is seen is content to see or play, a document to open or a thing to find out: the decider reads it.
SEEN_PLACE_MARKERS = frozenset(
    {
        "lo de", "lo del", "eso de", "eso del", "algo de", "algo del", "la parte de", "la parte del", "la seccion de",
        "la seccion del", "el apartado de", "el apartado del", "el menu de", "el menu del", "la pestana de",
        "la pestana del", "las opciones de", "las opciones del", "los ajustes de", "los ajustes del",
        "la configuracion de", "la configuracion del",
        "the stuff of", "the stuff about", "the part of", "the part about", "the section of", "the section about",
        "the settings for", "the settings of", "the options for", "the menu for", "stuff about", "the page for",
    }
)
# ---------------------------------------------------------------- a switch said by an ambiguous verb (computer use)
# Ronda 20 P8 (v3-33 «sacá una captura de pantalla completa» read as a switch turned off): a switch is always a thing
# already there, said definite. These verbs mean turning off or on only before a definite object («sacá el modo
# oscuro», «poné la vista previa», «sacale lo de …»); before any other they get or make a thing («sacá una copia»,
# «quitá una fila», «poné una alarma», «take a screenshot»).
# Review 3 of r20 P8 (blocker 3): only the verbs the reading already took for a switch, now narrowed to a definite
# object. «ponele», «put on», «take off», «sacame» or «quitame» before a definite object mostly give or take a thing
# («ponele el nombre informe», «ponele el volumen al máximo», «put on the music»): never a switch, free reading.
TOGGLE_AMBIGUOUS_OFF_VERBS = frozenset({"saca", "quita"})
TOGGLE_AMBIGUOUS_ON_VERBS = frozenset({"pon", "pone", "poneme"})
# What makes the object of such a verb definite.
TOGGLE_DEFINITE_LEADS = frozenset({"el", "la", "los", "las", "the", "lo de"})
# What makes an object indefinite or counted: never a switch, whatever the verb («desactivá un filtro»).
INDEFINITE_LEADS = frozenset(
    {
        "un", "una", "unos", "unas", "uno", "otro", "otra", "otros", "otras", "algun", "alguna", "algunos",
        "algunas", "a", "an", "another", "some",
    }
)

# ---------------------------------------------------------------- a new container of a named kind (computer use)
# Ronda 20 P8 (v3-37 «abrí una pestaña nueva de símbolo del sistema» read as going to «nueva de simbolo del sistema»):
# the containers a window opens anew, and the words that say a new one. Neither is ever part of a place's name.
CONTAINER_NOUNS = frozenset({"pestana", "tab", "solapa", "ventana", "window"})
# How the goal names each container («abrir una pestaña nueva de X»).
CONTAINER_GOAL_NOUNS = {"pestana": "pestaña", "tab": "pestaña", "solapa": "pestaña", "ventana": "ventana", "window": "ventana"}
NOVELTY_WORDS = frozenset({"nueva", "nuevo", "otra", "otro", "new", "another"})
# Review 3 of r20 P8 (blocker 2): a word of novelty says a new thing only after an indefinite article («una nueva
# carpeta», «a new window») or beside a container's noun («la pestaña nueva»); those of them that are indefinite
# themselves («otra carpeta», «another window») say it alone. «new york», «nueva carpeta» (a folder's name), «new
# releases» stay names.
INDEFINITE_ARTICLES = frozenset({"un", "una", "unos", "unas", "a", "an"})
INDEFINITE_NOVELTY_WORDS = frozenset({"otra", "otro", "otras", "otros", "another"})
# ---------------------------------------------------------------- a question that points back at what was just shown
# Ronda 20b (v3-50 t2 «decime cuántos archivos tiene adentro» after «en 7zip abrí el prueba.zip…»): the words of a
# question about the inside of what the mission before opened, what it holds or what it says, with no subject or place
# of its own. The word closes the question: «¿qué contiene la vitamina C?», «¿qué incluye una dieta keto?» or «¿qué
# tiene adentro un huevo?» name their own subject, «dentro de X» / «inside of X» their own place, and «¿qué tiene una
# manzana adentro?» puts a subject between the verb and «adentro» (contracasos r20b-3). ``missions.anaphoric_question``
# reads it; ``missions.follow_up_in_application`` reads such a question in the conversation's application.
INSIDE_WORDS = frozenset({"adentro", "dentro", "inside", "within"})
INSIDE_VERBS = frozenset({"tiene", "tienen", "hay", "habia", "lleva", "trae", "is", "s", "are", "has", "have"})
HOLDS_WORDS = frozenset({"contiene", "contienen", "contains", "contain", "incluye", "incluyen", "includes", "include"})
SAYS_WORDS = frozenset({"dice", "dicen", "pone", "ponen", "muestra", "muestran", "say", "says", "show", "shows"})
_QUESTION_END = r"(?=[\s¿?¡!.,;:]*$)"
ANAPHORIC_QUESTION = (
    rf"\b{alternation(INSIDE_VERBS)}\s+(?:ahi\s+|there\s+)?{alternation(INSIDE_WORDS)}{_QUESTION_END}"
    rf"|\b{alternation(HOLDS_WORDS)}{_QUESTION_END}"
    rf"|\b(?:que|what)\s+(?:(?:does|do)\s+(?:it|that|this)\s+)?{alternation(SAYS_WORDS)}{_QUESTION_END}"
    rf"|\b(?:in|on)\s+(?:it|there){_QUESTION_END}"
)
# Revisión 3 de r20b-3 («¿el último correo qué dice?», «el correo de Ana, ¿qué dice?», «the clipboard, what is in it?»
# after «abrí Spotify»): a subject said BEFORE the question has its own thing too. Before its interrogative word (or the
# words above, when no interrogative heads it) an anaphoric question carries only these: a link, a verb of telling, a
# filler, a pointing word. Any other word (an article, a noun, «my») is a subject of its own.
ANAPHORIC_LEAD_WORDS = frozenset({
    "y", "e", "o", "ahora", "luego", "despues", "entonces", "tambien", "mismo", "ok", "okay", "bueno", "oye", "che",
    "pues", "a", "ver", "porfa", "favor", "por", "baxy",
    "decime", "dime", "digame", "deci", "contame", "cuentame", "avisame", "fijate", "mira", "mirame", "lo", "todo",
    "ahi", "aca", "aqui", "alli", "alla", "eso", "esto",
    "and", "now", "then", "also", "so", "well", "hey", "please", "tell", "me", "let", "know", "show", "check", "read",
    "there", "here", "it", "that", "this", "all",
})
# Ronda 23 (r21 v3-50 t2 «decime cuántos archivos tiene adentro» was framed «en 7-Zip File Manager, …» and «prueba.zip»
# was lost: the engine counted the folder). A holding verb asked with nothing after it («¿qué tiene?», «¿qué traen?»)
# asks it of what the turn before named; ``dialogue.leans_on_context`` reads it with ``ANAPHORIC_QUESTION``.
BARE_HOLDING_VERBS = frozenset({"tiene", "tienen", "trae", "traen", "lleva", "llevan"})
# The extensions a file is named with («prueba.zip», «informe final.docx»): ``dialogue.named_objects`` reads a file
# named by one; web addresses («youtube.com») end in none of them.
FILE_EXTENSIONS = frozenset({
    "txt", "md", "csv", "json", "xml", "log", "ini", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods",
    "odp", "rtf", "png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "tif", "tiff", "ico", "mp3", "wav", "flac", "ogg",
    "m4a", "mp4", "mkv", "avi", "mov", "webm", "zip", "rar", "7z", "tar", "gz", "exe", "msi", "bat", "ps1", "py", "js",
    "html", "htm", "css", "iso", "tgz", "bz2", "xz", "cab", "img", "vhd", "vhdx",
})
# Revisión 2 de r23 («¿cuántos archivos hay adentro?» after «abrí la carpeta Descargas y seleccioná foto.jpg» was sent
# «… (foto.jpg)»: count inside a picture): only a file that holds others — an archive or a disk image — has an inside a
# question can ask of. ``dialogue.objective_with_the_antecedent_object`` keeps no other file for such a question.
CONTAINER_EXTENSIONS = frozenset({
    "zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "cab", "iso", "img", "vhd", "vhdx",
})
# Revisión 2 de r23: a turn before that named a place of its own («la carpeta Descargas», a path) leaves the inside a
# follow-up asks of ambiguous between that place and a file in it; ``dialogue.objective_with_the_antecedent_object``
# repairs nothing then.
PLACE_NOUNS = frozenset({
    "carpeta", "carpetas", "folder", "folders", "directorio", "directory", "ruta", "path", "unidad", "drive",
})
ANAPHORIC_QUESTION_HEAD = (
    r"\b(?:que|cual|cuales|cuanto|cuanta|cuantos|cuantas|como|donde|cuando|quien|quienes|hay|"
    r"what|which|how|where|when|who|is|are|does|do)\b"
)
