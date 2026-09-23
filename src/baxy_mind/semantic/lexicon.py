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

# ---------------------------------------------------------------- restoring the system sound (audio.mute, muted = false)
# Held-out 2026-09-22 «devolvele el sonido»: giving the sound back is unmuting it.
# Each verb with the clitics people fuse to it («devolveme», «devuélvenos», «restaurale»), generated once.
_AUDIO_RESTORE_VERBS = ("devuelve", "devolve", "devolver", "restaura", "restaurar", "recupera", "recuperar")
AUDIO_RESTORE_WORDS = frozenset(
    {verb + clitic for verb in _AUDIO_RESTORE_VERBS for clitic in ("", "me", "le", "les", "nos", "lo")}
)
AUDIO_RESTORE = alternation(AUDIO_RESTORE_WORDS)
