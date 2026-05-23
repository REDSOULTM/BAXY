"""Per-language STT profiles for Whisper.

WHY (2026-05-22, pedido del user): el `initial_prompt` y el `language` de
Whisper estaban hardcodeados a español ("español rioplatense"). Un usuario que
habla inglés u otro idioma se topaba con un prompt español que lo perjudicaba.
Gemma 4 es multi-usuario / multi-idioma (regla de uso universal), así que la
config de STT debe ser POR IDIOMA.

DISEÑO (basado en investigación 2024-2025):
  - El `initial_prompt` de Whisper funciona como CONTINUACIÓN de estilo, no como
    instrucción. Listar nombres propios + ejemplos en el idioma-matriz sesga al
    modelo hacia ellos. La puntuación/capitalización del prompt se traslada al
    output. (Sotto blog; arxiv 2406.05806 "Do Prompts Really Prompt?".)
  - Para CODE-SWITCHING (ej. español con apps en inglés: "abre Spotify"), lo
    correcto es FIJAR el idioma-matriz (`language="es"`) y dejar que los nombres
    propios en inglés fluyan por subwords. Autodetect es PEOR: Whisper flipea de
    idioma a mitad de frase y no vuelve. (openai/whisper discussions #2009, #49;
    arxiv 2412.16507 "Language-Aware Decoding".)
  - Por eso cada perfil = (código de idioma fijo) + (prompt en ESE idioma con
    los nombres propios — que son agnósticos del idioma — embebidos).

Fuentes:
  - https://sotto.to/blog/improve-whisper-accuracy-prompts
  - https://arxiv.org/html/2406.05806v1  (prompts = style continuation)
  - https://arxiv.org/html/2412.16507v2  (code-switching, language-aware decode)
  - https://github.com/openai/whisper/discussions/2009  (CS flip-back failure)

Cada perfil expone:
  - `whisper_language`: código ISO que se pasa a faster-whisper (fijo, no auto).
  - `frame(apps, artists, songs) -> str`: arma el initial_prompt en ese idioma.

Para agregar un idioma nuevo: añadir una entrada a `PROFILES`. Los nombres de
apps/artistas/canciones vienen del inventario (agnóstico de idioma) y se inyectan
igual en todos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

# Cap conservador del initial_prompt (<224 tokens de Whisper). ~880 chars.
PROMPT_CHAR_CAP = 880


@dataclass(frozen=True)
class LangProfile:
    code: str                       # clave interna ("es", "en", ...)
    whisper_language: str           # lo que se pasa a Whisper (fijo)
    label: str                      # humano, para logs/UI
    # frame(apps, artists, songs) -> initial_prompt en el idioma-matriz.
    frame: Callable[[list[str], list[str], list[str]], str]


def _join_list(label: str, items: list[str], sep: str = ", ") -> str:
    return f"{label}: {sep.join(items)}. " if items else ""


def _frame_es(apps: list[str], artists: list[str], songs: list[str]) -> str:
    # Español como idioma-matriz; nombres de apps/canciones en inglés embebidos.
    # Los ejemplos BILINGÜES (mismo comando ES + EN) sesgan contra la
    # fonetización de anglicismos ("Spotify"->"espotifai", "Chrome"->"crom") —
    # técnica clave para Spanglish: el modelo ve el nombre propio escrito en
    # inglés en contexto y lo mantiene en vez de transcribirlo fonéticamente.
    # Ejemplos con los nombres propios DIFÍCILES en posición de comando — donde
    # más sesgan al decoder. MEDIDO sobre 300 clips (real+sintético) 2026-05-22:
    # poner Steam/YouTube/Netflix/Disney/HBO/Counter-Strike en los EJEMPLOS hace
    # que Whisper los oiga bien EN EL ORIGEN ("Show2V"->YouTube, "ponse
    # tranquete"->"pon Stranger Things en Netflix") — mucho mejor que corregir
    # downstream. Validado contra el eval completo (no el bench n=6 viejo que
    # daba señal ruidosa). Seed bilingüe ES+EN para anti-fonetización.
    head = (
        "Conversación con el asistente Gemma en español, con nombres de "
        "aplicaciones, juegos y servicios en inglés. "
        "Hey Gemma, abre Chrome. Hey Gemma, open Chrome. "
        "Hey Gemma, abre Steam. Hey Gemma, abre YouTube. "
        "Hey Gemma, pon Stranger Things en Netflix. "
        "Hey Gemma, pon House of the Dragon en HBO Max. "
        "Hey Gemma, reproduce Daredevil en Disney Plus. "
    )
    body = (
        _join_list("Apps", apps[:25])
        + _join_list("Artistas", artists[:8])
        + _join_list("Canciones", songs[:5])
    )
    tail = (
        "Comandos breves en español con nombres de apps y servicios en inglés, "
        "dirigidos al asistente Gemma."
    )
    return head + body + tail


def _frame_en(apps: list[str], artists: list[str], songs: list[str]) -> str:
    head = (
        "Conversation with the assistant Gemma in English, with application, "
        "game and song proper nouns. "
        "Hey Gemma, open Chrome. Hey Gemma, play Spotify. "
        "Hey Gemma, play Daredevil on Disney Plus. "
    )
    body = (
        _join_list("Apps", apps[:25])
        + _join_list("Artists", artists[:10])
        + _join_list("Songs", songs[:6])
    )
    tail = "Short spoken commands to the assistant Gemma."
    return head + body + tail


def _frame_pt(apps: list[str], artists: list[str], songs: list[str]) -> str:
    head = (
        "Conversa com o assistente Gemma em português, com nomes de "
        "aplicativos, jogos e músicas em inglês. "
        "Hey Gemma, abre o Chrome. Hey Gemma, toca o Spotify. "
    )
    body = (
        _join_list("Apps", apps[:25])
        + _join_list("Artistas", artists[:10])
        + _join_list("Músicas", songs[:6])
    )
    tail = "Comandos curtos em português dirigidos ao assistente Gemma."
    return head + body + tail


def _frame_fr(apps: list[str], artists: list[str], songs: list[str]) -> str:
    head = (
        "Conversation avec l'assistant Gemma en français, avec des noms "
        "d'applications, de jeux et de chansons en anglais. "
        "Hey Gemma, ouvre Chrome. Hey Gemma, mets Spotify. "
    )
    body = (
        _join_list("Applications", apps[:25])
        + _join_list("Artistes", artists[:10])
        + _join_list("Chansons", songs[:6])
    )
    tail = "Commandes courtes en français adressées à l'assistant Gemma."
    return head + body + tail


PROFILES: dict[str, LangProfile] = {
    "es": LangProfile("es", "es", "Español (Spanglish)", _frame_es),
    "en": LangProfile("en", "en", "English", _frame_en),
    "pt": LangProfile("pt", "pt", "Português", _frame_pt),
    "fr": LangProfile("fr", "fr", "Français", _frame_fr),
}

DEFAULT_LANG = "es"


def resolve_lang(lang: str | None = None) -> str:
    """Resuelve el código de idioma a usar:
      1. `lang` explícito si es válido.
      2. env GEMMA4_VOICE_LANG.
      3. DEFAULT_LANG.
    Acepta variantes ("es-419", "en-US") tomando el prefijo de 2 letras.
    """
    for candidate in (lang, os.environ.get("GEMMA4_VOICE_LANG")):
        if not candidate:
            continue
        code = str(candidate).strip().lower().replace("_", "-").split("-")[0]
        if code in PROFILES:
            return code
    return DEFAULT_LANG


def get_profile(lang: str | None = None) -> LangProfile:
    return PROFILES[resolve_lang(lang)]
