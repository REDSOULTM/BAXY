"""Turn-level mode selection for the Gemma 4 agent."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


# Per-call LLM timeout is DERIVED from the mode's token budget, so it can't
# drift from the actual work. Floor decode speed = the slowest realistic case
# (CPU-bound / contended GPU ~20 tok/s; measured floor, real is 40-70). Prefill
# headroom covers the ~5-8K-token system prompt + tool schemas being processed.
# Clamped so a tiny reply still gets a sane minimum and a long one doesn't run
# to the global 180s default.
_FLOOR_TOK_S = 20.0          # worst realistic decode tok/s
_PREFILL_HEADROOM_S = 12.0   # process system prompt + tools + connect/health
_MIN_CALL_TIMEOUT_S = 20.0
_MAX_CALL_TIMEOUT_S = 150.0


@dataclass(frozen=True)
class AgentMode:
    name: str
    enable_thinking: bool
    parallel_tool_calls: bool
    max_tokens: int
    system_hint: str
    # Cap on reasoning tokens when enable_thinking is True. -1 = unbounded.
    # MEASURED: with thinking unbounded, some turns generate 13k-15k reasoning
    # tokens — at ~50 tok/s on CPU that's MINUTES, blowing the 4-5s voice
    # budget. A simple action only needs ~90 reasoning tokens to emit the
    # tool-call, so action modes cap tight; research/deep keep a larger budget
    # for genuine multi-step reasoning. llama.cpp honors this via
    # `thinking_budget_tokens` in the request body (verified on build b9090).
    thinking_budget: int = -1
    # SAMPLING POR MODO. Los defaults de Gemma (T=1.0/top_p=0.95/top_k=64) son
    # para chat/thinking; en modos de ACCIÓN con gramática activa son
    # innecesariamente altos y dan varianza turno-a-turno en el nombre de la tool
    # y los args. Una T más baja en acción estabiliza sin empobrecer el lenguaje
    # (esos modos emiten tool-call o summary corto, no prosa larga). None = usar
    # el default del config (sin override). NO se aplica cuando el cliente ya va
    # greedy (la decisión de tool-call manda con temp=0). Práctica de industria:
    # greedy/baja-T para JSON estructurado y function-calling.
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None

    @property
    def request_timeout_s(self) -> float:
        """Per-call wall-clock deadline derived from this mode's token budget.

        Without a per-call cap the main LLM call inherits the global 180s
        default, so a hung/slow turn blocks the user for up to
        max_agent_turns * 180s. For a voice assistant, failing fast and letting
        the user re-ask beats a multi-minute freeze. The bound scales with the
        work the mode actually permits (tokens), at the slowest realistic
        decode speed, so it never trips on a legitimately long reply."""
        budget_tokens = self.max_tokens + max(0, self.thinking_budget)
        est = budget_tokens / _FLOOR_TOK_S + _PREFILL_HEADROOM_S
        return float(max(_MIN_CALL_TIMEOUT_S, min(_MAX_CALL_TIMEOUT_S, est)))


MODE_NAMES = {"auto", "fast_action", "fast_info", "quick_action", "deep_action", "vision_action", "audio_mode", "research"}


def choose_mode(content: str | list[dict[str, Any]], configured: str, base_max_tokens: int) -> AgentMode:
    """Choose conservative defaults for the current user turn."""

    configured = (configured or "auto").strip().casefold()
    if configured not in MODE_NAMES:
        configured = "auto"

    inferred = configured if configured != "auto" else _infer_mode(content)
    # Control fino sobre thinking para evitar el CUDA crash (llama.cpp issue
    # #22527). Por default thinking sigue ON pero con budget MUY chico (32
    # tokens, lo minimo para emitir el tool-call). Esto mantiene fiabilidad de
    # tool-call sin acumular KV que dispara el bug.
    # GEMMA4_FORCE_THINKING_OFF=1 → thinking OFF total (defensa extrema).
    import os as _os_th2
    _force_off = _os_th2.environ.get(
        "GEMMA4_FORCE_THINKING_OFF", "0").strip().lower() in {"1","true","yes","on"}
    _allow_thinking = not _force_off
    if inferred == "research":
        return AgentMode(
            name="research",
            enable_thinking=_allow_thinking,
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
    if inferred == "fast_info":
        # Preguntas informativas que el modelo responde de su conocimiento
        # paramétrico (explica/compara/diferencia/por qué/qué es), SIN necesidad
        # de retrieval web. MEDIDO (E4B-Q6 en vivo): thinking ON en estas
        # preguntas es PURO costo de latencia y A MENUDO PEOR calidad — el
        # reasoning se come el budget y deja content VACÍO (finish=length):
        # "fotosíntesis" OFF 0.73s correcto vs ON 7.2s VACÍO; "RAM vs disco" OFF
        # 7.1s correcto vs ON VACÍO; "GTA5" OFF 0.44s vs ON 4.81s. Para recall
        # factual el thinking NO aporta. Por eso: thinking OFF + hint conciso de
        # voz + max_tokens moderado (evita el muro de markdown verboso que el
        # modelo escupe sin guía). Estas preguntas, ruteadas a `research`
        # (thinking ON, 2048 tok), eran el origen de outliers de 15-48s.
        return AgentMode(
            name="fast_info",
            enable_thinking=False,
            parallel_tool_calls=False,
            max_tokens=min(base_max_tokens, 320),
            system_hint=_INFO_HINT,
            # Algo de variance para razonamiento breve factual, pero por
            # debajo del default 1.0 (recall factual no necesita creatividad).
            temperature=0.6, top_p=0.95, top_k=40,
        )
    if inferred == "vision_action":
        return AgentMode(
            name="vision_action",
            enable_thinking=_allow_thinking,
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
            enable_thinking=_allow_thinking,
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
        # MEDIDO (E4B-Q4): con thinking OFF Gemma4 emite el tool-call solo ~2/6
        # veces (promete en texto); con thinking ON, 6/6. El razonamiento es lo
        # que hace fiable el tool-calling en Gemma4. El costo es ~+1s de latencia
        # (0.8s -> 1.7s LLM), holgado bajo el budget 4-5s. Por eso un comando de
        # acción usa thinking ON, pero con el budget chico de fast_action
        # (respuesta corta estilo voz) y su mismo system_hint.
        # thinking_budget MUY BAJO (32 tokens) para mantener la fiabilidad del
        # tool-call SIN acumular el KV cache que dispara el CUDA crash (llama.cpp
        # issue #22527). MEDIDO:
        #  - thinking=True budget 256 → crashes en turn 2-3
        #  - thinking=False → tool-call falla 4/10 (LLM no emite)
        #  - thinking=True budget 32 → balance: tool-call OK + crash retrasado
        # Gate: GEMMA4_FORCE_THINKING_OFF=1 fuerza OFF (defensa extrema).
        return AgentMode(
            name="quick_action",
            enable_thinking=_allow_thinking,
            parallel_tool_calls=False,
            max_tokens=min(base_max_tokens, 512),
            system_hint=_FAST_ACTION_HINT + _frcot_hint(),
            thinking_budget=32 if _allow_thinking else 256,
        )
    # fast_action: smalltalk + confirmaciones cortas ("hola", "gracias",
    # "Listo, abrí Spotify"). MEDIDO: un "hola" generaba 512 tokens (el modelo
    # no encuentra stop y divaga) -> 512 * 24.5 ms = 12.5 s con el 26B
    # (~40 tok/s), la causa del "se demora 10s en un hola".
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
        # smalltalk/confirmaciones cortas -> baja-T estabiliza la respuesta
        # sin empobrecerla (son 1-2 frases). Reduce varianza turno-a-turno.
        temperature=0.4, top_p=0.9, top_k=40,
    )


# Info questions (fast_info): concise voice-style prose, NO markdown, thinking
# OFF. Same anti-verbosity rules as research's reply-format but without the web
# retrieval framing (these answer from parametric knowledge).
_INFO_HINT = (
    "Mode: fast_info. You are a VOICE assistant. Answer the question DIRECTLY in "
    "1-3 short sentences of plain prose. NO markdown, NO bullets, NO **bold**, NO "
    "headers '#', NO numbered lists, NO emojis. If the user asks for a concrete "
    "fact (date, name, number), give it FIRST in one sentence, then at most one "
    "short clarifying sentence. Do not pad. Ej: 'GTA 5 salió el 17 de septiembre "
    "de 2013.' o 'La RAM es memoria volátil y rápida para datos en uso; el disco "
    "es almacenamiento permanente y más lento.'"
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


# FR-CoT (Function-Routing Chain-of-Thought): para modelos chicos, un thinking
# BREVE y ESTRUCTURADO es más fiable Y más rápido que el thinking libre.
# Evidencia: Qi 2026 (arXiv 2604.02155, BFCL v3) — brief CoT@32 sube tool-call
# de 44%->64% en Qwen2.5-1.5B y baja alucinación a 0%. NUESTRO E4B genera
# p90=268 / max=841 tok de thinking (hasta 4.3s); esto lo acota a ≤4 líneas.
# Gate GEMMA4_FRCOT=0 lo desactiva (las cifras son de Qwen, NO de Gemma —
# MEDIR tokens antes/después en nuestro modelo, por eso reversible).
_FRCOT_HINT = (
    "\n\nTHINKING: razoná BREVE, máximo 4 líneas, en este formato exacto, "
    "luego emití el tool-call:\n"
    "INTENT: <abrir_app|reproducir|control_sistema|buscar|aclarar>\n"
    "TOOL: <nombre exacto de la función, o none>\n"
    "ARGS: <clave=valor separados por coma, o —>\n"
    "GO\n"
    "Nunca deliberes más de esas 4 líneas. Si no podés decidir el tool/args, "
    "INTENT=aclarar y hacé UNA pregunta corta sin llamar tools."
)


def _frcot_hint() -> str:
    # DEFAULT OFF (medido en NUESTRO E4B, no Qwen): FR-CoT MEJORA apps/audio
    # (audio 5.2s->2.4s, 11/12->12/12) PERO REGRESIONA media (6/6->3/6,
    # 7.3s->10.5s): Gemma E4B a veces emite el formato INTENT/TOOL/ARGS como
    # TEXTO DE SALIDA en vez de en el canal de pensamiento, y eso rompe el
    # tool-call. Las cifras de Qi 2026 eran de Qwen, no Gemma — y acá se ve la
    # diferencia. Net negativo -> opt-in (=1) para experimentar, NO default
    # (el formato no sobrevivió en el dominio media).
    import os as _os
    if (_os.environ.get("GEMMA4_FRCOT", "0").strip().lower()
            not in {"1", "true", "yes", "on"}):
        return ""
    return _FRCOT_HINT


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

    # Queries informativas (explicaciones, comparaciones, listas, cronologias)
    # necesitan budget grande. fast_action con max_tokens=384 trunca
    # mid-sentence en respuestas de 2+ parrafos. Markers ya estan "folded"
    # (lowercase + sin acentos) porque `low` paso por _fold_text.
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
    # Interrogativas factuales SIN verbo de acción: "cuándo salió GTA 5",
    # "quién escribió X", "cuántos planetas hay". El router a veces ofrece tools
    # de acción por una palabra clave del objeto ("GTA" -> game_launcher), lo que
    # disparaba upgrade-a-thinking + forced-retry y volvía lento un turno que es
    # SOLO una pregunta de conocimiento (medido 16s). Si hay palabra
    # interrogativa y NINGÚN verbo de acción (action_score==0, ya chequeado
    # arriba), es fast_info. NOTA: el `?` no es requisito (el STT a veces no lo
    # transcribe); detectamos por palabra interrogativa folded.
    question_markers = (
        " cuando ", " quien ", " quienes ", " cuanto ", " cuantos ", " cuantas ",
        " cual ", " cuales ", " donde ", " que es ", " que son ", " que fue ",
        " a que ", " en que ano ", " en que año ",
    )
    if action_score == 0 and any(m in low for m in question_markers):
        return "fast_info"

    if any(m in low for m in info_markers):
        # Info question answered from knowledge (no web). thinking OFF — measured
        # faster AND higher quality than research-mode thinking (which left empty
        # replies). Genuine retrieval ("buscame info", "noticias", "actual")
        # already returned "research" above.
        return "fast_info"

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
