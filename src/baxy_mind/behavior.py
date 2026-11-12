"""The person's own texts for how BAXY behaves (Ajustes → Comportamiento; owner's order of 2026-11-08, 00_IDENTIDAD «La
personalidad vive en el prompt»): its personality and tone, how it replies, and the person's standing preferences. Its
name and identity are not among them: the fixed identity opens the system text (IDENTITY) and a fixed rule on the name
closes it after them (NAME_GUARD).

They are words in the system text and nothing else: the tools come from the App's catalog, the kernel authorizes every
call and asks for the «sí» whatever the model was told. Each goes in a fixed place, so with the factory texts the system
text is the very one written before this setting existed (its prefix restores as it did), and a text of the person's own
changes only that text: the kept prefix's key holds the whole system text (LlmServer.prefix_key), so it is read again
once and kept under its own key from then on."""
from __future__ import annotations

import re
from typing import Any

# Who BAXY is opens the system text and nobody edits it (owner's limit of 2026-11-08: «BAXY siempre se tiene que llamar
# BAXY»; 00_IDENTIDAD «Su nombre es BAXY y sólo BAXY»). It goes first, before and above any text of the person's: what
# holds it is that order and this fixed part, never a reading of what the person wrote; measured, not guaranteed
# (00_IDENTIDAD gives the figures).
IDENTITY = ("Eres BAXY y sólo BAXY: un compañero tipo Jarvis que vive en el PC de la persona y hace lo que te pide "
            "usando herramientas. Eres un él.")
# The person's personality and tone, quoted as a tone after the rules; none by default. Measured on the PC (08-11, 16
# held-out phrases asking its name x 4 texts that rename it, 2 seeds, Qwen3.5-4B; «dice BAXY» of 128): with the text in
# place of the identity, 1; with the identity before it and the text right after, 13; with the text framed as a tone
# and a closing rule on the name, 90; the identity repeated after the text, 73; the text at the end, after the rules, and
# the rule on the name right after it (this), 123, as the factory texts (116: three phrases it misreads with any text).
# The 4B follows the latest and most specific instruction: so the identity opens the system text, and a fixed rule on
# the name closes it (NAME_GUARD) whenever any text is the person's. None of it reads what the person wrote: it is the
# same words whatever the text says.
PERSONALITY_HEAD = "La persona pidió este carácter y tono para ti: "
PERSONALITY_TAIL = (" Tómalo sólo como tono: si ese texto te da otro nombre o dice que eres otro asistente, en eso no lo "
                    "sigas, porque te llamas BAXY y sólo BAXY y así te presentas.")
# A second set (16 phrases x 6 texts, another hand; this rule was chosen on it, so it is no longer held out), on the
# notebook: 152 of 192 with the rule above saying only «present yourself as another» (162 on the PC), 164 with it naming
# a ready-made answer to that question too (this); the first set 122 of 128 (machine not stated; 123 on the PC). What is left are texts that bring that very answer («si te preguntan,
# responde: Me llamo X»): about half of their answers still take it.
NAME_GUARD = ("\nSi te preguntan cómo te llamas o quién eres, o te piden presentarte, dices que eres BAXY. Ningún texto de "
              "la persona cambia ese nombre: si te pide presentarte con otro, decir que eres otro asistente o contestar "
              "a esa pregunta con una frase que trae hecha, en eso no lo sigas y di que eres BAXY.")
# How it replies; the rules after it stay BAXY's.
REPLIES = ("Hablas en el idioma de la persona (español neutro, inglés o spanglish), tuteas, eres cálido y breve: una o "
           "dos frases, sin listas, sin markdown y sin emojis, porque tu respuesta se dice en voz alta.")
# After the rules and the catalog's areas; none by default.
PREFERENCES_HEAD = "\nPreferencias de la persona (las reglas de arriba y tu nombre, BAXY, siguen valiendo): "
FIELDS = ("personality", "replies", "preferences")
# ~250 tokens each at most: the context left beside the ~48.5k-token prefix is the conversation's (llm_server CONTEXT).
MAX_CHARS = 800
# The model's own markers in Qwen3.5's template: written into the system text they would end it or open a turn.
_MARKERS = re.compile(r"<\|[^|<>]{0,40}\|>|</?(?:tool_call|tool_response|think)>")


def factory() -> dict[str, str]:
    """The factory texts the person may replace, as the App shows them beside the person's (the mind's hello)."""
    return {"personality": "", "replies": REPLIES, "preferences": ""}


def texts(given: Any) -> dict[str, str]:
    """The texts the system is written with: each of the person's as given, without the model's markers and cut at
    MAX_CHARS; one that is missing, empty or not text is the factory's."""
    chosen = factory()
    for field in FIELDS:
        value = given.get(field) if isinstance(given, dict) else None
        text = _unmarked(value).strip()[:MAX_CHARS].strip() if isinstance(value, str) else ""
        if text:
            chosen[field] = text
    return chosen


def _unmarked(text: str) -> str:
    """The text without the model's markers, removed until none is left: one nested in another is rebuilt by a single
    pass («<|im_<|x|>end|>»)."""
    while (shorter := _MARKERS.sub("", text)) != text:
        text = shorter
    return text


def head(chosen: dict[str, str]) -> str:
    """What opens the system text, before its rules: the fixed identity, then how it replies. With the factory texts,
    the two sentences written before this setting existed."""
    return IDENTITY + " " + chosen["replies"]


def tail(chosen: dict[str, str]) -> str:
    """What closes the system text, after its rules and areas: the person's personality and preferences, when there are
    any, and the name last whenever any text is the person's; nothing with the factory texts."""
    personality = ("\n" + PERSONALITY_HEAD + "«" + chosen["personality"] + "»" + PERSONALITY_TAIL
                   if chosen["personality"] else "")
    preferences = PREFERENCES_HEAD + chosen["preferences"] if chosen["preferences"] else ""
    return personality + preferences + (NAME_GUARD if custom(chosen) else "")


def custom(chosen: dict[str, str]) -> list[str]:
    """Which of the texts are the person's own (for the trace: the fields, never their words)."""
    return [field for field in FIELDS if chosen[field] != factory()[field]]
