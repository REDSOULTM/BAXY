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
SOUND_BACK = (
    rf"(?:{AUDIO_RESTORE}|vuelve|volve|vuelva|regresa|regrese)\s+(?:(?:el|la|the|mi|my)\s+)?(?:sonido|audio|sound)"
)

# ---------------------------------------------------------------- the mute as a switch (audio.mute)
# Uso real 2026-09-23 «Turn off silenciar»: the mute said as a thing that is switched off (muted = false) or on
# (muted = true), in Spanish, English or both. «quitá el silencio» was read before; the other switches were not.
_MUTE_STATE_NOUN = r"(?:(?:el|la|the)\s+)?(?:modo\s+)?(?:mute|silencio|silenciar|mudo|silence|silent(?:\s+mode)?)"
MUTE_SWITCH_OFF = (
    r"(?:turn(?:ed)?\s+off|switch\s+off|apaga(?:r|le)?|desactiva(?:r|le)?|disable|deactivate|"
    r"quita(?:r|le)?|saca(?:r|le)?|remove)\s+" + _MUTE_STATE_NOUN
)
MUTE_SWITCH_ON = r"(?:turn\s+on|switch\s+on|activa(?:r|le)?|enciende|prende|enable)\s+" + _MUTE_STATE_NOUN
# Tanda 4 2026-09-24 «Enciende el sound» was answered as a limit: the sound itself switched on is the mute
# switched off (muted = false), and the sound switched off is the mute on (muted = true), in Spanish, English or
# both. Only the sound, the audio or the PC's own sound is the object: «enciende la música» plays, «apaga el PC»
# shuts down, «prende los parlantes» may be a Bluetooth device.
_SOUND_NOUN = r"(?:(?:el|la|los|the|mi|my)\s+)?(?:sonido|sonidos|sound|sounds|audio)(?:\s+(?:del?|of)\s+(?:(?:el|la|the|mi|my)\s+)?(?:pc|equipo|computador(?:a)?|computer|sistema|system))?"
_SOUND_ON_VERB = (
    r"(?:turn(?:ed)?\s+on|switch\s+on|enable|activa(?:r|le)?|enciende(?:le)?|encende(?:le)?|encender|prende(?:le)?|"
    r"prender|habilita(?:r)?)"
)
_SOUND_OFF_VERB = r"(?:turn(?:ed)?\s+off|switch\s+off|disable|apaga(?:r|le)?|desactiva(?:r|le)?|deshabilita(?:r)?)"
# The sound ends the order: «desactiva el sonido de las notificaciones» is another sound.
_SOUND_ORDER_END = (
    r"(?=\s*(?:[,.;:!?]|$|\s(?:y|and|por\s+favor|porfa|please|ya|ahora|now|de\s+nuevo|again|otra\s+vez)\b))"
)
SOUND_SWITCH_ON = rf"(?:{_SOUND_ON_VERB}\s+{_SOUND_NOUN}|turn\s+{_SOUND_NOUN}\s+on){_SOUND_ORDER_END}"
SOUND_SWITCH_OFF = rf"(?:{_SOUND_OFF_VERB}\s+{_SOUND_NOUN}|turn\s+{_SOUND_NOUN}\s+off){_SOUND_ORDER_END}"

# Uso real 2026-09-23 «silencio»: the bare silence order, the whole message. MASSIVE audio_volume_mute (dev corpus
# 2026-09-23) «silencio altavoces», «altavoces en silencio»: the silence with the speakers or the sound it falls on,
# still with no verb.
_SILENCED_OBJECT = rf"(?:(?:los|las|el|la|the|mis|my)\s+)?(?:{SPEAKER_NOUN}|sonidos?|sounds?|audio)"
BARE_SILENCE = (
    r"^[¿?¡!\s]*(?:"
    rf"(?:silencio|mudo|silence|quiet)(?:\s+(?:(?:en|a|on|for)\s+)?{_SILENCED_OBJECT})?|"
    rf"{_SILENCED_OBJECT}\s+(?:en\s+)?(?:silencio|mudo|mute)"
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
# (web.names_own_data). The most common given names in Spanish and English. Left out on purpose: names that are also
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
