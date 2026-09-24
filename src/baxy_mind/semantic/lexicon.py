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

# Uso real 2026-09-23 «silencio»: the bare silence order, the whole message.
BARE_SILENCE = r"^[¿?¡!\s]*(?:silencio|mudo|silence|quiet)(?:\s+(?:total|por\s+favor|porfa|please|ya|ahora))?[\s.!?]*$"

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
MUTE_REQUEST = rf"^[¿?¡!\s]*(?:{SOUND_BACK}|{MUTE_SWITCH_OFF}|{MUTE_SWITCH_ON}|{NOISE_STOP})\b|{BARE_SILENCE}"
