"""Turn-level mode selection for the Gemma 4 agent."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentMode:
    name: str
    enable_thinking: bool
    parallel_tool_calls: bool
    max_tokens: int
    system_hint: str
    # Cap on reasoning tokens when enable_thinking is True. -1 = unbounded.
    # MEASURED (2026-05-20): with thinking unbounded, some turns generate
    # 13k-15k reasoning tokens — at ~50 tok/s on CPU that's MINUTES, blowing
    # the 4-5s voice budget. A simple action only needs ~90 reasoning tokens
    # to emit the tool-call, so action modes cap tight; research/deep keep a
    # larger budget for genuine multi-step reasoning. llama.cpp honors this
    # via `thinking_budget_tokens` in the request body (verified on b9090).
    thinking_budget: int = -1


MODE_NAMES = {"auto", "fast_action", "quick_action", "deep_action", "vision_action", "audio_mode", "research"}


def choose_mode(content: str | list[dict[str, Any]], configured: str, base_max_tokens: int) -> AgentMode:
    """Choose conservative defaults for the current user turn."""

    configured = (configured or "auto").strip().casefold()
    if configured not in MODE_NAMES:
        configured = "auto"

    inferred = configured if configured != "auto" else _infer_mode(content)
    if inferred == "research":
        return AgentMode(
            name="research",
            enable_thinking=True,
            parallel_tool_calls=True,
            max_tokens=max(base_max_tokens, 2048),
            system_hint=(
                "Mode: research. Use web(...) for extracted sources. You may use multiple "
                "independent web/search tool calls in one assistant turn, but do not claim "
                "facts without returned source evidence. "
                "REPLY FORMAT: voice assistant style. 2-4 frases corridas en texto plano. "
                "NO markdown, NO bullets, NO **bold**, NO headers '#', NO listas numeradas. "
                "Solo el dato pedido en prosa fluida. Si el user pide algo factual "
                "concreto (fecha, nombre, precio), respondé eso primero en UNA frase, "
                "después una breve elaboración si aporta. Ej: 'GTA 5 salió el 17 de "
                "septiembre de 2013 en PS3 y Xbox 360. La versión de PC llegó en 2015.'"
            ),
            thinking_budget=2048,  # research reasons more, but cap the runaway
        )
    if inferred == "vision_action":
        return AgentMode(
            name="vision_action",
            enable_thinking=True,
            parallel_tool_calls=False,
            max_tokens=max(base_max_tokens, 1600),
            system_hint=(
                "Mode: vision_action. Use screenshots/images as evidence before GUI actions. "
                "Prefer UIA when available, then screenshot/vision, then raw GUI."
            ),
            thinking_budget=1024,
        )
    if inferred == "audio_mode":
        return AgentMode(
            name="audio_mode",
            enable_thinking=False,
            parallel_tool_calls=False,
            max_tokens=max(base_max_tokens, 1280),
            system_hint=(
                "Mode: audio_mode. Treat attached audio as user evidence. If transcription is "
                "uncertain, say so instead of inventing details."
            ),
        )
    if inferred == "deep_action":
        return AgentMode(
            name="deep_action",
            enable_thinking=True,
            parallel_tool_calls=False,
            max_tokens=max(base_max_tokens, 2048),
            system_hint=(
                "Mode: deep_action. Execute multi-step PC missions in order. Think privately, "
                "act, observe, verify, then continue until the sequence is done or blocked."
            ),
            thinking_budget=1024,  # multi-step needs more, but still bounded
        )
    if inferred == "quick_action":
        # quick_action: comando de UNA sola acción ("abre steam", "pon música").
        # MEDIDO (2026-05-20, E4B-Q4): con thinking OFF Gemma4 emite el tool-call
        # solo ~2/6 veces (promete en texto); con thinking ON, 6/6. El
        # razonamiento es lo que hace fiable el tool-calling en Gemma4. El costo
        # es ~+1s de latencia (0.8s -> 1.7s LLM), holgado bajo el budget 4-5s.
        # Por eso un comando de acción usa thinking ON, pero con el budget chico
        # de fast_action (respuesta corta estilo voz) y su mismo system_hint.
        return AgentMode(
            name="quick_action",
            enable_thinking=True,
            parallel_tool_calls=False,
            max_tokens=min(base_max_tokens, 512),
            system_hint=_FAST_ACTION_HINT,
            thinking_budget=384,  # enough to decide+emit a tool-call (~90 obs)
        )
    # fast_action: smalltalk + confirmaciones cortas ("hola", "gracias",
    # "Listo, abrí Spotify"). MEDIDO (log de sesión): un "hola" generaba 512
    # tokens (el modelo no encuentra stop y divaga) -> 512 * 24.5 ms = 12.5 s
    # con el 26B (~40 tok/s). ESO es el "se demora 10s en un hola".
    # Una respuesta conversacional de voz real es ~10-40 tokens. Capamos a 128
    # (worst case: 128/40 = 3.2s en el 26B; 128/80 = 1.6s en E4B) — holgado
    # bajo el budget 4-5s en CUALQUIER perfil. El system_hint ya pide "1-2
    # frases MAX", así que 128 nunca trunca una respuesta legítima de voz.
    # Si el usuario pide algo largo (explica/compara/investiga), _infer_mode
    # lo manda a research/deep_action, que mantienen su budget alto.
    return AgentMode(
        name="fast_action",
        enable_thinking=False,
        parallel_tool_calls=False,
        max_tokens=min(base_max_tokens, 128),
        system_hint=_FAST_ACTION_HINT,
    )


# Shared by fast_action (smalltalk, thinking off) and quick_action (single
# command, thinking on) — same voice-assistant reply style, different
# reasoning budget.
_FAST_ACTION_HINT = (
    "Mode: fast_action. You are a VOICE assistant — Alexa/Jarvis style. "
    "Reply in 1-2 sentences MAX, plain text. NO markdown, NO bullet "
    "lists, NO headers, NO emojis, NO disclaimers, NO 'te recomiendo X'. "
    "Direct facts only. If the user asks 'cuando salio GTA 5' say "
    "'17 de septiembre de 2013' — punto. No bullets, no extra context. "
    "If a tool just finished successfully in this turn, ONE confirmation: "
    "'Listo, X.' (replace X with the concrete action, e.g. 'Listo, abrí Spotify'). "
    "If NO tool ran in this turn (small-talk, thanks, greetings, "
    "answering a question), respond naturally and DO NOT use 'Listo' "
    "as an ack — 'gracias' deserves 'de nada' or 'no hay de qué', "
    "not 'Listo'."
)


def _infer_mode(content: str | list[dict[str, Any]]) -> str:
    text, has_image, has_audio = _content_summary(content)
    low = f" {_fold_text(text)} "
    if has_image:
        return "vision_action"
    if has_audio:
        return "audio_mode"

    research_markers = (
        " investiga ",
        " investigar ",
        " fuentes ",
        " fuente ",
        " internet ",
        " noticia ",
        " noticias ",
        " actual ",
        " actualiza ",
        " actualizado ",
        " ultimo ",
        " ultima ",
        " reciente ",
        " busca informacion ",
        " buscame informacion ",
        " que se sabe ",
    )
    if any(marker in low for marker in research_markers):
        return "research"

    sequencing_markers = (
        " luego ",
        " despues ",
        " entonces ",
        " primero ",
        " por ultimo ",
        " y luego ",
        " and then ",
        " then ",
    )
    action_markers = (
        " abre ",
        " ve a ",
        " busca ",
        " pon ",
        " escribe ",
        " instala ",
        " mueve ",
        " copia ",
        " crea ",
        " ejecuta ",
    )
    sequence_score = sum(1 for marker in sequencing_markers if marker in low)
    action_score = sum(1 for marker in action_markers if marker in low)
    if sequence_score or action_score >= 2 or len(text) > 180:
        return "deep_action"
    # Single-action command ("abre steam", "pon música", "saca screenshot").
    # MEASURED: these need thinking ON to emit the tool-call reliably (2/6 OFF
    # vs 6/6 ON) — route to quick_action (thinking on, voice-concise) instead
    # of fast_action (thinking off). Smalltalk has no action marker -> still
    # fast_action.
    if action_score >= 1:
        return "quick_action"

    # F-004: queries informativas (explicaciones, comparaciones, listas,
    # cronologias) necesitan budget grande. fast_action con max_tokens=384
    # trunca mid-sentence en respuestas de 2+ parrafos. Markers ya estan
    # "folded" (lowercase + sin acentos) porque `low` paso por _fold_text.
    info_markers = (
        " explica ", " explicame ", " explicar ",
        " describ ", " describime ", " describeme ",
        " compara ", " comparar ", " comparame ",
        " orden ", " lista ", " cronolog ",
        " diferencia ", " diferencias ",
        " porque ", " por que ",
        " razon ",
        " resumi ", " resumime ", " resumen ",
        " todos los ", " todas las ",
        " pasos para ", " como funciona ",
    )
    if any(m in low for m in info_markers):
        return "research"

    return "fast_action"


def _fold_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _content_summary(content: str | list[dict[str, Any]]) -> tuple[str, bool, bool]:
    if isinstance(content, str):
        return content, False, False
    text_parts: list[str] = []
    has_image = False
    has_audio = False
    for part in content:
        kind = str(part.get("type") or "")
        if kind == "text":
            text_parts.append(str(part.get("text") or ""))
        elif kind == "image_url":
            has_image = True
        elif kind == "input_audio":
            has_audio = True
    return " ".join(text_parts), has_image, has_audio
