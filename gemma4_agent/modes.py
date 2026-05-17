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


MODE_NAMES = {"auto", "fast_action", "deep_action", "vision_action", "audio_mode", "research"}


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
        )
    # fast_action: smalltalk + confirmaciones cortas. base_max_tokens default
    # (1280) era excesivo — a ~50 tok/s eso es 25s worst case si el modelo no
    # encuentra stop. Capamos a 384 que cubre 95% de respuestas conversacionales
    # (~7-8s wall clock max). Si el usuario quiere respuestas largas, el router
    # lo manda a deep_action / research que mantienen su budget alto.
    return AgentMode(
        name="fast_action",
        enable_thinking=False,
        parallel_tool_calls=False,
        max_tokens=min(base_max_tokens, 384),
        system_hint=(
            "Mode: fast_action. You are a VOICE assistant — Alexa/Jarvis style. "
            "Reply in 1-2 sentences MAX, plain text. NO markdown, NO bullet "
            "lists, NO headers, NO emojis, NO disclaimers, NO 'te recomiendo X'. "
            "Direct facts only. If the user asks 'cuando salio GTA 5' say "
            "'17 de septiembre de 2013' — punto. No bullets, no extra context. "
            "If a tool finished, ONE confirmation: 'Listo, X.' Nothing more."
        ),
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
