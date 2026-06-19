"""Agent loop: Gemma 4 decides, tools execute, results are fed back."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..safety_pkg import reply_validator
from ..infra.config import AgentConfig
from ..support.evaluator import evaluate_mission
from ..infra.llm_client import LLMClient
from ..memory_pkg.memory import MemoryStore
from ..support.modes import AgentMode, choose_mode
from ..tools_pkg.multimodal import image_part, user_content
from ..routing.planner import MissionPlan, plan_mission, select_tool_names
from ..support.reasoning import build_action_to_tool, detect_leaked_tool_call, sanitize_assistant_message, sanitize_text
from ..memory_pkg.state import AgentState
from ..tools_pkg.tools import ToolRegistry
from ..infra.tracing import TraceLogger, summarize_content

logger = logging.getLogger(__name__)


ProgressCallback = Callable[[str, dict[str, Any]], None]


# ── "BAXY NETO" (rama Experimentando) ────────────────────────────────────────
# GEMMA4_GUARDS=0 (DEFAULT acá) DESACTIVA todos los guards de COMPORTAMIENTO del
# turn-path para ver al modelo crudo: honestidad (unverified_final + grounded_action_
# claim), forced_tool_retry, leaked-call rescue, redes deterministas y empty-reply net.
# Para RESTAURARLOS: GEMMA4_GUARDS=1. NOTA: sanitize_text NO es un guard (es
# decodificación de salida) y queda SIEMPRE activo. Con el split (FunctionGemma=tools,
# Q4 QAT=habla) estos guards eran compensación del E2B; se sacan para probar neto.
import os as _os_guards
_GUARDS_ON = _os_guards.environ.get("GEMMA4_GUARDS", "0").strip().lower() in {"1", "true", "yes", "on"}

# ── FunctionGemma run9 como ROUTER DE TOOL-CALLING (split) ───────────────────
# GEMMA4_FG_ROUTER=1 → FunctionGemma-270M (:8082) decide el tool-call en vez del E2B;
# `no_tool` (abstención) → responde el E2B conversacional. El E2B sigue siendo el que
# CONVERSA; FunctionGemma solo elige tool+args. Requiere GEMMA4_LEAN_TOOLS=0 (el router
# jerárquico usa las 67 familias) + el server FG en 127.0.0.1:8082. Default OFF (drop-in
# reversible). Ver gemma4_agent/routing/fg_router.py + FunctionGemma/INTEGRATION_HANDOFF.md.
#
# FUNCIÓN (no constante de módulo): apply_profile_to_env() escribe GEMMA4_FG_ROUTER al
# ACTIVAR un perfil (p.ej. vram4_lean), lo que puede pasar DESPUÉS de importar este módulo
# (orden del launcher). Si fuera constante leída al import, el flag quedaría viejo y el perfil
# lean NO activaría el router. Leyendo el env en cada llamada, funciona sin importar el orden.
def _fg_router_on() -> bool:
    return _os_guards.environ.get("GEMMA4_FG_ROUTER", "0").strip().lower() in {"1", "true", "yes", "on"}


# Inherit-tools safety knobs.
# TTL: si pasaron mas de 5 min entre turns, NO heredar tools del turno
# previo (el contexto del usuario pudo cambiar tras un hueco largo).
INHERIT_TTL_SEC = 300
# Tools nunca-heredables por safety: una respuesta corta del user
# ("ok", "si") jamas debe disparar uno de estos sin re-confirmacion.
DANGEROUS_TOOLS_NEVER_INHERIT = frozenset({
    "whatsapp", "whatsapp_send",
    "file_delete", "file_write",
    "system_shutdown", "system_logoff", "system_restart",
    "subprocess", "shell",
})
# Tools que dejan una tarea INTERACTIVA abierta (una app en pantalla esperando
# input). Si el turno previo ejecutó una de estas, una continuación deíctica corta
# ("hacelo tú", "seguí", "dale") está retomando ESA tarea — aunque el abstain head
# la lea como conversacional. El estado del SO (app abierta, objetivo incompleto)
# es evidencia estructural de que el turno está mid-flight; pesa más que el clasificador
# de texto. Universal: no depende del idioma ni del nombre de la app.
_GUI_CONTEXT_TOOLS = frozenset({"gui", "uia", "app", "window", "vision"})

# Tope de re-prompts forzados por turno cuando, en movilidad/no_vidente, el LLM
# DELEGA la tarea en el usuario en vez de seguir actuando. Acota el "hacé todo
# por el usuario" para que el 4B no se cuelgue en una cadena infinita: avanza
# hasta este tope y, si no completó, para honesto. Cada re-prompt consume además
# una iteración del loop max_agent_turns, así que esto es un límite ADICIONAL.
import os as _os_a11y
_A11Y_MAX_CONTINUES = int(_os_a11y.environ.get("GEMMA4_A11Y_MAX_CONTINUES", "3"))

# Confirmación/negación a la oferta de automatización proactiva. El
# "sí/no" es vocabulario CERRADO y universal -> lista multilingüe (no embeddings:
# 1-2 palabras dan señal pobre). Cubre los idiomas más comunes; lo no reconocido
# NO se consume (cae a None, el turno sigue normal). La app la usa cualquier
# hablante -> nada de solo-español. [[feedback_no_monolingual_regex]]
_JARVIS_YES = frozenset({
    # es
    "si", "sí", "dale", "bueno", "hacelo", "hazlo", "automatizalo", "automatízalo",
    "claro", "obvio", "ok", "okay", "vale", "sip", "correcto", "exacto",
    # en
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please", "definitely",
    # pt
    "sim", "claro", "isso", "faz", "pode",
    # fr
    "oui", "ouais", "vas-y", "daccord",
    # de
    "ja", "klar", "gerne", "mach",
    # it
    "sì", "certo", "fallo",
})
_JARVIS_NO = frozenset({
    # es
    "no", "nop", "negativo", "mejor", "despues", "después", "nada",
    # en
    "no", "nope", "nah", "dont", "later", "skip",
    # pt
    "não", "nao", "depois",
    # fr
    "non", "pas",
    # de
    "nein", "nö", "später",
    # it
    "no", "dopo",
})


# CORE-SET para PREFIJO ESTABLE del prompt (latencia).
# El system prompt + tool-schemas se filtran al subset que el router elige por
# turno; como el subset cambia con la query, el INICIO del prompt cambia y ROMPE
# el prefix-cache de llama.cpp -> cada turno reprocesa ~1100ms en vez de ~100ms
# (medido: prefijo estable reusado = 101ms vs prefijo cambiado = 1036ms, 10x).
# Fix: anteponer SIEMPRE un core-set fijo (en orden fijo) a los picks del router,
# así el prefijo (reglas+schemas del core) es idéntico turno-a-turno y el cache
# lo reusa. Los picks extra del router van DESPUÉS (siguen disponibles para el
# modelo). El orden es FIJO (no sorted del subset variable) — esa es la clave.
# Grounding: los 15 tools más llamados en logs reales + verify/filesystem
# de infraestructura. ~4956 tokens estables, deja ~11K de 16K ctx para historial.
# Gate: GEMMA4_STABLE_TOOL_PREFIX (default ON; =0 vuelve al comportamiento viejo).
_CACHE_CORE_SET: tuple[str, ...] = (
    "app", "window", "gui", "media", "steam", "web", "browser",
    "whatsapp", "contacts", "audio", "system", "office", "filesystem",
    "state", "verify", "session", "memory",
)


def _stabilize_tool_order(picks: list[str]) -> list[str]:
    """Devuelve core-set (orden FIJO) + picks del router que no estén en core.

    Estabiliza el prefijo del prompt para maximizar el prefix-cache. El core va
    primero SIEMPRE en el mismo orden (de ahí el cache-hit); los extras del
    router quedan al final (varían, pero ya no rompen el prefijo del core)."""
    import os as _os
    # DEFAULT OFF (medido): el core-set fijo estabiliza el prefijo y
    # baja el prefill en AISLADO (1126->100ms), PERO en el smoke E2E real salió
    # ~2x MÁS LENTO (audio 3.4s OFF vs 6.5s ON): el prompt más grande (17 tools
    # fijos vs 4-6 del router) infla ~3000 tok/turno y el historial creciente
    # rompe el cache en la cola igual, así que el ahorro no compensa. El router
    # ya da subsets chicos que se cachean cuando se repiten. Se deja como opt-in
    # (=1) para experimentar, pero NO es la solución de latencia: la teoría del
    # prefix-cache no sobrevivió al E2E real (medir, no celebrar).
    if (_os.environ.get("GEMMA4_STABLE_TOOL_PREFIX", "0").strip().lower()
            not in {"1", "true", "yes", "on"}):
        return picks
    if not picks:
        return picks  # smalltalk / no-tools: no inflar con el core-set
    seen = set(_CACHE_CORE_SET)
    extras = [t for t in picks if t not in seen]
    return list(_CACHE_CORE_SET) + extras


# CORE_PROMPT + TOOL_RULES + build_system_prompt + SYSTEM_PROMPT
# moved to :mod:`.agent_prompt`. Re-export keeps existing callers (tests,
# ui/, server.py /agent/system_prompt endpoint, mcp_server) working.
from .agent_prompt import (  # noqa: E402,F401
    CORE_PROMPT,
    SYSTEM_PROMPT,
    TOOL_RULES,
    build_system_prompt,
)
from .turn_types import TurnDecision


@dataclass
class ToolEvent:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentReply:
    content: str
    tool_events: list[ToolEvent] = field(default_factory=list)
    error: str | None = None
    mission: dict[str, Any] | None = None
    # True when the reply prose was already streamed to the TTS sink
    # sentence-by-sentence during generation (GEMMA4_STREAM_TTS). The voice
    # runner uses this to avoid re-feeding `content` (which would double-speak).
    tts_streamed: bool = False


# Detección de idioma del reply post-tool extraída a lang_detect.py (split
# archivo-dios 2026-06-19). Re-exportada para reply_repair / agent_runner, que la
# importan desde `.agent`.
from .lang_detect import (  # noqa: E402,F401
    _FIXED_LANGS,
    _IMPERATIVE_VERBS,
    _LANG_NAMES,
    _LANGID_SET,
    _SPANISH_LEAK_MARKERS,
    _detect_lang,
    _detect_lang_is_strong,
    _looks_spanish,
    _os_ui_lang,
    _reply_lang,
)


# Sufijo del buffer sanitizado que PUEDE ser la apertura de un token especial
# Gemma a medio llegar ('<', '<|', '<|tool_ca', '<unus'): el streamer TTS lo
# retiene hasta que el próximo delta lo desambigüe — markup confirmado ('<|')
# aborta el feed; prosa legítima ('2 < 3') se libera intacta. Ver el markup
# guard en _chat_streaming (2026-06-10).
import re as _re_tts_markup
_TTS_MARKUP_OPENER_TAIL_RE = _re_tts_markup.compile(r"<[|a-z_]*$",
                                                    _re_tts_markup.IGNORECASE)


def _stream_tts_enabled() -> bool:
    """Stream the reply to TTS sentence by sentence (GEMMA4_STREAM_TTS).
    Default OFF: voice must match the final chat reply unless this experimental
    low-latency path is explicitly enabled. Solo afecta modo voz:
    _stream_this exige _active_tts_sink (texto/GUI/CLI pasan tts_sink=None ->
    no-op)."""
    import os as _os_stream
    return (
        _os_stream.environ.get("GEMMA4_STREAM_TTS", "0") or "0"
    ).strip().lower() in {"1", "true", "yes", "on"}


def _summary_keep_tools_enabled() -> bool:
    """Keep the tool schemas in the SUMMARY pass so its prompt PREFIX stays
    byte-identical to pass-1 -> the llama.cpp prefix-cache HITS instead of
    re-prefilling ~5k tokens. **Default ON, validated live.**

    Why both fixes are needed: keep-tools ALONE looks like a loss (pass-2 still
    re-prefills 5919) because a SECOND prefix divergence — toggling
    `enable_thinking` in chat_template_kwargs (pass-1 True / summary False) —
    re-renders the template from token ~0 (MEASURED cache_n=4). With BOTH fixed
    (keep tools + match enable_thinking, success-gated in _execute_turn), pass-2
    prefill drops 5229->82 tokens, ~1s saved per successful action turn. SOAK: 7/8
    cache hits, 0 runaways, replies correct. Cache-mode is SUCCESS-GATED (failures
    use the slim/thinking-off path — enable_thinking=True makes the model re-engage
    with a failed action). Toggle off with GEMMA4_SUMMARY_KEEP_TOOLS=0."""
    import os as _os_skt
    return (
        _os_skt.environ.get("GEMMA4_SUMMARY_KEEP_TOOLS", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


# Gates de latencia (fast_info/research/experience) + señal de idioma rápida +
# decisión research-profunda extraídos a latency_helpers.py (2026-06-09, ratchet
# archivo-dios: la tanda de latencia los habría engrosado en agent.py). Re-export
# con los nombres privados que el resto del módulo usa.
from .latency_helpers import (  # noqa: E402
    fast_info_no_tools_enabled as _fast_info_no_tools_enabled,
    research_fast_search_enabled as _research_fast_search_enabled,
    experience_cold_load_enabled as _experience_cold_load_enabled,
    should_keep_full_web_research as _should_keep_full_web_research,
)


def _error_recovery_enabled() -> bool:
    """Recuperación por TIPO de error. Cuando una tool falla
    (confirmed=False), en vez del nudge genérico "reintentá", clasificamos el error
    (missing_precondition/param_mismatch/transient) y damos una directiva ESPECÍFICA
    para que el loop se auto-corrija (replan/amend) o pare honesto (skip). Capa
    GENÉRICA (el LLM decide la recuperación), no macro-por-intención. Opt-in
    GEMMA4_ERROR_RECOVERY, default ON (validado en vivo + suite verde;
    kill-switch GEMMA4_ERROR_RECOVERY=0). Sin costo por-turno: sólo
    actúa en el path de fallo de una tool, no en el hot-path de cada turno."""
    import os as _os_er
    return (
        _os_er.environ.get("GEMMA4_ERROR_RECOVERY", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _memory_tools_enabled() -> bool:
    """Tool-picking guiado por memoria. Agrega al subset las
    tools que tuvieron ÉXITO en turnos PASADOS con intención similar (experience
    recall por embedding, ya computado en _recent_recalls). El LLM sigue decidiendo
    si llamarlas; sólo ensanchamos los candidatos (como exemplar/semantic), así una
    tool que funcionó antes está disponible aunque el router no la elija hoy.
    GEMMA4_MEMORY_TOOLS default ON; kill-switch =0. SEGURO: latency-free
    (reusa _recent_recalls, ya computado para el recall_hint — sin embed extra); el recall
    es TIGHT (max_distance=0.9≈cos0.55, anti-degradation) → solo agrega tools de éxitos
    GENUINAMENTE similares; cap=3; el 4B decide; no-op si no hay historial relevante."""
    import os as _os_mt
    return (
        _os_mt.environ.get("GEMMA4_MEMORY_TOOLS", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _skills_autoinject_enabled() -> bool:
    """Trigger-inject de skills. MEDIDO: el 4B nunca emite skill_load
    (0/5 directo, 0/6727 prod) — no hace el meta-paso cargar->seguir. En vez de
    esperar skill_load, inyectamos la receta de la skill que matchea semánticamente
    el pedido (como microagents). GEMMA4_SKILLS_AUTOINJECT default ON
    (validado en vivo: el 4B SIGUE la receta — screenshot->gui+vision, backup->backup_sync+
    filesystem, research->web; 0 falsos positivos /10; kill-switch =0). Perf OK: costo real
    ~2-4ms MEDIANA < budget 5ms; el embed del user-text es cache-hit (el router corre antes
    de _system_message, mismo LRU) + scan_skills cacheado. El perf-test mide mediana, no
    la media (un pico aislado de ~6ms es flake del suite en box degradado, no costo real)."""
    import os as _os_sk
    return (
        _os_sk.environ.get("GEMMA4_SKILLS_AUTOINJECT", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _recalled_success_tools(recalls: list | None, exclude, cap: int = 3) -> list[str]:
    """Tools de recalls EXITOSOS (status sin 'FAIL') que NO estén ya en `exclude`,
    deduplicadas y capadas a `cap`. Los recalls fallidos son lección de 'evitar'
    (no se agregan). Pura para testear sin LLM/box."""
    out: list[str] = []
    excl = set(exclude or [])
    for r in (recalls or []):
        rr = r or {}
        status = str(rr.get("outcome_code") or rr.get("mission_status") or "").upper()
        if "FAIL" in status:
            continue
        for t in (rr.get("tools_used") or []):
            if t and t not in excl and t not in out:
                out.append(t)
                if len(out) >= cap:
                    return out
    return out


# --- File-by-extension routing override ---
# Ruteo de tools por extensión de archivo extraído a file_routing.py (split
# archivo-dios 2026-06-19). Re-exportado para los métodos de esta clase.
from .file_routing import (  # noqa: E402,F401
    _file_processor_on,
    _file_tool_routing_enabled,
    _route_file_by_extension,
)


class _FinalizeContinue:
    """Sentinel returned by Gemma4Agent._finalize_turn when the a11y
    nudge re-prompted the LLM and the caller must `continue` its
    outer for _turn loop. Single instance: _FINALIZE_CONTINUE.
    """
    __slots__ = ()


_FINALIZE_CONTINUE = _FinalizeContinue()


class Gemma4Agent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.memory = MemoryStore(self.config.memory_path)
        self.state = AgentState(self.config.state_path)
        self.client = LLMClient(self.config)
        self.tools = ToolRegistry(self.memory, self.config.captures_dir, self.state, safety_enabled=self.config.enable_safety)
        # Wire subagent delegation: the `subagent` tool needs to spawn a fresh
        # Gemma4Agent. We give the registry a back-reference so it can call us.
        self.tools.parent_agent = self  # type: ignore[attr-defined]
        self.trace = TraceLogger(self.config.trace_path, self.config.enable_tracing)
        # Camino C dinamico: lanzar background recompute del set
        # CORE_TOOL_RULE_NAMES desde el trace historico. La sesion actual ya
        # se inicializo con el set leido al import-time de agent_prompt; este
        # bg recompute persiste el set adaptado para la PROXIMA sesion. No
        # bloquea el boot, no rompe el cache de esta sesion.
        try:
            from .core_tools_pareto import maybe_recompute_in_background
            maybe_recompute_in_background(self.config.trace_path)
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger(__name__).debug(
                "core_tools_pareto bg recompute failed: %s", _exc,
            )
        # TTL purge of stale closed resources on startup so
        # state.json doesn't accumulate zombie entries forever. Wrapped in
        # try/except — purge MUST NEVER break boot.
        try:
            _purge = self.state.purge_stale_closed(max_age_days=7)
            if _purge.get("purged", 0) > 0:
                self.trace.event("startup", "state_purge", **_purge)
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "state.json purge_stale_closed failed: %s", _exc,
            )
        # Bug medido: un `pending_intent` (tool aparcado el turno
        # anterior esperando respuesta del usuario) es una señal de continuidad
        # DENTRO de la misma sesión — se evalúa contra `_turn_counter`, que
        # vuelve a 0 en cada proceso nuevo. Pero set_pending_intent lo PERSISTE
        # en state.json; al reiniciar, su `created_turn` es de un contador que ya
        # no existe y el primer turno (counter=1) lo ve "fresco" para siempre.
        # Síntoma real: un computer_use aparcado sin args en una sesión vieja
        # secuestraba "¿quién eres?" del arranque (forzaba computer_use + toda la
        # unión semántica; en modo movilidad terminaba en screenshot+OCR para
        # responder identidad — absurdo). Una aclaración aparcada y nunca resuelta
        # antes de cerrar la sesión está ABANDONADA: la limpiamos al boot. Las
        # aclaraciones legítimas (preguntar→responder) viven y mueren dentro de
        # un mismo proceso, donde el TTL por turnos sí aplica. Best-effort.
        try:
            if hasattr(self.state, "get_pending_intent") and hasattr(
                self.state, "clear_pending_intent"
            ):
                # Leer crudo (sin TTL, que depende del counter) directo del store.
                _stale_pi = (self.state._load() or {}).get("_pending_intent")
                if _stale_pi:
                    self.state.clear_pending_intent()
                    self.trace.event(
                        "startup", "pending_intent_cleared_on_boot",
                        tool=str((_stale_pi or {}).get("tool") or ""),
                        asks_for=str((_stale_pi or {}).get("asks_for") or ""),
                    )
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "state.json pending_intent clear-on-boot failed: %s", _exc,
            )
        from ..memory_pkg.experience import ExperienceMemory
        self.experience = ExperienceMemory(self.config.memory_path.parent / "experience.sqlite")
        # Capa proactiva: log de comportamiento para detectar rutinas
        # del usuario y ofrecer automatizarlas. SEPARADO de experience (no
        # contamina). Best-effort: si falla, no rompe nada. Gate GEMMA4_JARVIS=0.
        import os as _os_j
        self._jarvis_on = _os_j.environ.get("GEMMA4_JARVIS", "1").strip().lower() \
            not in {"0", "false", "no", "off"}
        self.behavior = None
        self.ambient_observer = None
        self._pending_profile_forget = False  # confirmación de borrado de perfil
        if self._jarvis_on:
            try:
                from ..memory_pkg.behavior_log import BehaviorLog
                self.behavior = BehaviorLog()
                # Boot throttleado + retención: la política (gap, prune 60d) vive en
                # BehaviorLog.record_boot (F2/F3), no acá. Sin throttle la DB se
                # inflaba a ~21.4k boots en restart-loops y envenenaba al miner.
                self.behavior.record_boot()
            except Exception:
                self.behavior = None
            # Observador ambiente: la "capa viva" que mira el
            # comportamiento REAL del usuario (música via SMTC + app en foco) para
            # que Gemma4 aprenda quién es. Thread daemon, metadata-no-contenido,
            # gate GEMMA4_AMBIENT_OBSERVER. Best-effort: nunca rompe el boot.
            if self.behavior is not None:
                try:
                    from ..memory_pkg.ambient_observer import AmbientObserver
                    # JARVIS PROACTIVO (gate GEMMA4_JARVIS_PROACTIVE, default OFF):
                    # handler que, en cada transición de app, chequea si se completó
                    # un patrón conocido y sugiere automatizarlo por toast/voz — sin
                    # que el user escriba. Corre en el daemon (no toca el chat).
                    _transition_handler = None
                    try:
                        import os as _os_jp
                        # ON por default (user 2026-06-07): se apaga con
                        # GEMMA4_JARVIS_PROACTIVE=0.
                        if (_os_jp.environ.get("GEMMA4_JARVIS_PROACTIVE") or "1").strip().lower() \
                                not in {"0", "false", "no", "off"}:
                            from ..memory_pkg.jarvis_proactive import (
                                make_transition_handler, build_routine_from_candidate)
                            _transition_handler = make_transition_handler(
                                self.behavior,
                                create_routine=lambda c: build_routine_from_candidate(self.tools, c))
                    except Exception:
                        _transition_handler = None
                    self.ambient_observer = AmbientObserver(
                        self.behavior, on_app_transition=_transition_handler)
                    self.ambient_observer.start()
                except Exception:
                    self.ambient_observer = None
        # WATCHDOG de VRAM: muestrea VRAM libre con TTL para detectar
        # presión ANTES de despachar visión y evitar el OOM que deja a
        # llama-server zombie (issue #13085). No-op sin GPU NVIDIA. Barato,
        # cabe en vram4. Self-check al boot = fail-loud (no degradar en silencio).
        try:
            from ..support.vram_watchdog import VRAMWatchdog
            self.vram_watchdog = VRAMWatchdog()
            _vsnap = self.vram_watchdog.snapshot(force=True)
            if _vsnap.available and _vsnap.level != "ok":
                logger.warning(
                    "VRAM watchdog boot: nivel=%s libre=%.0fMiB usado=%.0fMiB "
                    "(presión de VRAM al arranque; visión puede degradarse)",
                    _vsnap.level, _vsnap.free_mib, _vsnap.used_mib,
                )
            elif _vsnap.available:
                logger.info(
                    "VRAM watchdog boot: ok, libre=%.0fMiB", _vsnap.free_mib)
        except Exception:
            self.vram_watchdog = None
        self.history: list[dict[str, Any]] = []
        self._recent_recalls: list[dict[str, Any]] = []
        self._explicit_plan_text: str = ""
        self._explicit_plan_steps: list[str] = []
        self._phrase_fires: list[dict[str, Any]] = []
        # Nota transitoria (un turno) cuando el usuario acaba de cambiar el modo
        # de accesibilidad por voz: el LLM la usa para CONFIRMAR el cambio con
        # sus propias palabras (no hay frase enlatada). Se limpia tras el turno.
        self._a11y_switch_note: str = ""
        # Nota transitoria (un turno) para preguntas cortas que continúan un
        # turno informativo/research real. No responde por el LLM; solo fija el
        # contrato conversacional para que resuelva la elipsis desde el historial.
        self._info_followup_note: str = ""
        self._info_followup_prefetch_query: str = ""
        # Contador (por turno) de re-prompts forzados en movilidad/no_vidente
        # cuando el LLM DELEGABA la tarea en vez de seguir actuando. Acotado para
        # "avanzar lo más posible y después parar honesto", sin colgarse.
        self._a11y_continue_count: int = 0
        # Summarization cooldown so we don't spend an extra LLM call every
        # turn when the conversation has just been compacted. Resets per-clear.
        self._summarize_last_run_turn: int = -10
        self._fact_extract_last_run_turn: int = -10
        self._turn_counter: int = 0
        # Diagnostics for the current turn (visible in traces; surfaced to the
        # user only when the final reply looks empty so they are not left in
        # the dark).
        self._explicit_plan_status: dict[str, Any] = {}
        # Persona: nudges system prompt + preferred tools. Default = no nudge.
        from ..support.personas import from_env as _persona_from_env
        self._persona = _persona_from_env()
        # Cache de microagents seleccionados a lo largo de la sesion.
        # Cuando un microagent matchea un turn, se agrega al cache y persiste
        # para siguientes turns (mantiene el KV cache caliente). agent.clear()
        # lo resetea junto con history.
        self._cached_microagents: list = []
        # Skills menu + critical block. Cacheado a nivel-instancia
        # porque el catalogo de skills es estatico (folder skills/ no cambia
        # mid-session). El KV cache del llama-server reutiliza el prefix.
        self._cached_skills_menu: str | None = None
        self._cached_skills_critical: str | None = None
        # Timestamp del ultimo turn cerrado, para TTL del inherit-tools
        # path (gap > 5 min => no heredar, evita disparar tools peligrosos
        # cuando se retoma la sesion tras mucho tiempo).
        self._last_turn_ts: float | None = None
        # The tools the PREVIOUS turn actually executed. Survives
        # history compaction (which strips tool messages), so a short
        # continuation ("subelo un poco mas") can inherit the real prior tool
        # instead of hallucinating. The history scan can't see these because
        # _compact_completed_history drops tool_calls/tool messages.
        self._last_executed_tools: list[str] = []
        # Entity ring para resolución deíctica
        # ("abrilo/ponelo/open it" -> el último path/url/id útil). Detección
        # multilingüe por embeddings (NO regex por idioma). Gated GEMMA4_DEICTIC.
        try:
            from ..routing.deictic_detector import EntityRing as _EntityRing
            self._entity_ring = _EntityRing(maxlen=5)
        except Exception:
            self._entity_ring = None
        self._mi_carry_tools: list[str] = []  # multi-intent: tools de contexto GUI a arrastrar
        # EAGER read-only (opt-in GEMMA4_EAGER_READONLY, default OFF): cache
        # per-turn de tools de SOLO-LECTURA pre-ejecutadas en background en
        # paralelo al pase-1 del LLM. Se crea/llena en _decide_turn y se
        # consume en el dispatch de _execute_turn. None = sin eager este turno.
        self._eager_cache = None
        # NOTE: NLI warmup at __init__ was REMOVED — it raced with the voice
        # stack (faster_whisper) loading huggingface_hub from another thread,
        # causing intermittent "cannot import name 'logging' from
        # huggingface_hub" errors on STT init. The classifier loads the NLI
        # model lazy-on-first-use; the first capability check pays the cold
        # load cost (~14s once per process), subsequent ones hit the cache.

        # FunctionGemma router: si está activo, pre-calentamos en BACKGROUND (botea
        # el server :8082 + construye el router) para que esté listo antes del 1er
        # turno sin bloquear el arranque. El 270M botea en ~2-3s. Daemon: no estorba
        # el shutdown. Idempotente (ensure_fg_server reusa si :8082 ya está vivo).
        if _fg_router_on():
            def _prewarm_fg() -> None:
                try:
                    from ..routing.fg_router import fg_emit
                    fg_emit("warmup")  # construye router (-> ensure_fg_server) + 1 pasada
                except Exception:
                    pass
            import threading as _thr
            _thr.Thread(target=_prewarm_fg, daemon=True, name="fg-prewarm").start()

    def _window_title_in_text(self, text: str) -> str | None:
        """Si alguna VENTANA ABIERTA tiene un token significativo de su título
        presente en `text`, devuelve ese título; si no, None. Señal de "el usuario
        habla de una app que YA está abierta" -> probablemente quiere operar dentro
        (computer-use), no relanzar. Universal: usa los títulos reales del SO, sin
        listas de apps ni idiomas. Best-effort (no-Windows / sin win32 -> None)."""
        import os as _os
        import re as _re
        if _os.name != "nt" or not text:
            return None
        # tokens del comando, sin stop-words cortas (>=4 chars para evitar ruido).
        toks = {w for w in _re.findall(r"\w+", text.lower()) if len(w) >= 4}
        if not toks:
            return None
        # REUSAR tools.list_windows (enumerador estable ya probado en prod) en vez
        # de un EnumWindows propio con callback efímero — ese daba error 126 (el GC
        # recolecta el callback antes de que ctypes lo use). list_windows devuelve
        # {ok, windows:[{title,...}]}.
        # LIMIT ALTO (bug medido): list_windows corta en `limit` (default
        # 30) y EnumWindows devuelve en Z-ORDER, que cambia entre llamadas (la ventana
        # al frente se mueve). Con 30, una app abierta (Discord) caía FUERA del corte
        # en llamadas sucesivas -> match INTERMITENTE (ok la 1ª vez, None las
        # siguientes). Acá buscamos UNA app puntual, no mostramos una lista: pedir
        # muchas ventanas para no perderla por el corte de Z-order.
        try:
            res = self.tools.list_windows({"limit": 200})
            wins = res.get("windows", []) if isinstance(res, dict) else []
        except Exception:
            return None
        for w in wins:
            t = str((w or {}).get("title") or "").strip()
            if not t:
                continue
            for wt in _re.findall(r"\w+", t.lower()):
                if len(wt) >= 4 and wt in toks:
                    return t
        return None

    # computer-use = tool del registry (tools.t_computer_use), NO un método del
    # agente. No hay short-circuit pre-LLM (secuestraba turnos). Los
    # helpers de abajo (_app_window_title/_title_now_matches/_quick_switcher_nav)
    # los reusa el PlanExecutor de computer_use.py.
    # Las macros por INTENCIÓN (in-app message/nav) están REEMPLAZADAS por la
    # capa universal de computer_use (el 4B planifica primitivas, un ejecutor las
    # corre). Medido: 16/16 en apps variadas. Los helpers
    # _quick_switcher_nav/_title_now_matches/_app_window_title siguen — los reusa
    # el PlanExecutor.
    def _app_window_title(self, win_hint: str) -> str:
        """Título ACTUAL de la ventana de la app (por el último token del hint, p.ej.
        'Discord'). Para verificar navegación-en-app por estado del SO. '' si no se
        puede leer (no-Windows / no encontrada)."""
        try:
            import win32gui as _w
            import re as _re_t
            toks = sorted((t for t in _re_t.findall(r"\w+", win_hint) if len(t) >= 4),
                          key=len, reverse=True)
            key = (toks[0] if toks else win_hint).lower()
            found = [""]
            def _cb(h, _):
                t = _w.GetWindowText(h) or ""
                if key in t.lower() and not t.lower().startswith("discord overlay"):
                    found[0] = t
                return True
            _w.EnumWindows(_cb, None)
            return found[0]
        except Exception:
            return ""

    def _title_now_matches(self, win_hint: str, target: str, title_before: str) -> bool:
        """True si el título de la ventana de la app refleja el target (= el chat/
        canal activo es el pedido). Señal de estado del SO, robusta al robo de foco
        post-click. Cuenta como éxito tanto si CAMBIÓ al target como si YA estaba en
        él (abrir un chat que ya estaba activo: igual está hecho)."""
        import re as _re_m
        after = self._app_window_title(win_hint)
        if not after:
            return False
        toks = [t for t in _re_m.findall(r"\w+", target.lower()) if len(t) >= 3]
        if not toks:
            return False
        # el título actual incluye el target -> estamos en el chat pedido (haya
        # cambiado o ya estuviéramos ahí). Es la prueba directa de estado del SO.
        return any(t in after.lower() for t in toks)

    def _quick_switcher_nav(self, win: str, target: str, turn_id: str) -> "AgentReply | None":
        """Navegar a un chat/canal/servidor por el QUICK-SWITCHER (Ctrl+K + nombre +
        Enter). Determinista, sin depender del árbol UIA ni de que el 4B encadene.
        Verifica por el TÍTULO de la ventana: si cambió e incluye una palabra del
        target, navegó. Devuelve AgentReply si confirmó, o None (que el caller dé su
        respuesta normal). Universal para apps de chat Electron; no hardcodea apps."""
        try:
            import win32gui as _w
        except Exception:
            return None
        def _title() -> str:
            try:
                return _w.GetWindowText(_w.GetForegroundWindow()) or ""
            except Exception:
                return ""
        try:
            from .. import gui_safety
            gui_safety.reset_action_budget()
            # enfocar (restaura si está minimizada) y leer el título base.
            self.tools._focus_window_chen(win)
            time.sleep(0.6)
            before = _title()
            # Ctrl+K abre el quick-switcher en Discord/Slack/Teams. (Si la app no lo
            # soporta, el type+Enter no cambia el título y devolvemos None.)
            self.tools.execute("gui", {"action": "keypress", "keys": "ctrl+k", "window": win})
            time.sleep(0.7)
            self.tools.execute("gui", {"action": "type", "text": target, "window": win, "method": "sendkeys"})
            time.sleep(1.0)
            self.tools.execute("gui", {"action": "keypress", "keys": "enter", "window": win})
            time.sleep(1.2)
            after = _title()
        except Exception:
            return None
        # VERIFY por estado del SO: el título ACTUAL incluye el target (= el chat/canal
        # activo es el pedido). matched cuenta tanto si cambió como si YA estabas ahí
        # (pediste un chat que ya estaba abierto: igual está hecho). 'changed' solo
        # informa para el caso ambiguo (navegó a algo pero sin matchear el target).
        import re as _re_qs
        changed = after != before
        toks = [t for t in _re_qs.findall(r"\w+", target.lower()) if len(t) >= 3]
        matched = any(t in after.lower() for t in toks) if toks else False
        self.trace.event(turn_id, "in_app_nav_quickswitcher",
                         window=win[:40], target=target[:40],
                         title_before=before[:40], title_after=after[:40],
                         changed=changed, matched=matched)
        events = [ToolEvent(name="gui",
                            args={"action": "quick_switcher", "target": target},
                            result={"ok": matched, "title_after": after,
                                    "verified": matched})]
        self._last_turn_ts = time.time()
        self._remember_executed_tools(events)
        _app = win.split(" - ")[-1] or win
        if matched:
            return AgentReply(content=f"Listo, abrí «{target}» en {_app}.",
                              tool_events=events, mission=None)
        if changed:
            # navegó a ALGO pero el título no matchea el target -> no confirmable.
            return AgentReply(
                content=f"Entré a algo en {_app} pero no pude confirmar que sea "
                        f"exactamente «{target}».",
                tool_events=events, mission=None)
        # el título no cambió ni matchea -> no navegó (target inexistente / no encontrado).
        return AgentReply(
            content=f"No encontré «{target}» en {_app}. ¿Está escrito igual que en la app?",
            tool_events=events, mission=None)

    def _remember_executed_tools(self, events: list[ToolEvent]) -> None:
        """Record the tool names this turn actually executed, so the NEXT
        turn's continuation-inherit can use them even after the tool messages
        are compacted out of history. Only meaningful tools (skip none)."""
        names: list[str] = []
        for e in events:
            nm = getattr(e, "name", None) or getattr(e, "tool", None)
            if isinstance(nm, str) and nm and nm not in names:
                names.append(nm)
            # ITEM 4: alimentar el entity ring con identificadores útiles del
            # result (path/url/id) — extracción estructural, best-effort.
            ring = getattr(self, "_entity_ring", None)
            if ring is not None:
                res = getattr(e, "result", None)
                if isinstance(res, dict):
                    try:
                        ring.push_from_result(str(nm or ""), res)
                    except Exception:
                        pass
        if names:
            self._last_executed_tools = names

    def clear(self) -> None:
        self.history.clear()
        self._recent_recalls = []
        self._summarize_last_run_turn = -10
        self._fact_extract_last_run_turn = -10
        self._turn_counter = 0
        self._cached_microagents = []
        self._last_executed_tools = []
        if getattr(self, "_entity_ring", None) is not None:
            self._entity_ring.clear()
        # Skills cache: reset para que scan_skills() vuelva a leer disk en el
        # proximo turn (util si el dev agrega/modifica un SKILL.md durante
        # desarrollo). En produccion el catalogo no cambia mid-session.
        self._cached_skills_menu = None
        self._cached_skills_critical = None
        self._last_turn_ts = None

    def set_persona(self, name: str) -> dict[str, Any]:
        """Switch the agent's persona by name. Returns the new persona info or an error dict."""
        from ..support.personas import PERSONAS, get
        if name and name.strip().casefold() not in PERSONAS:
            return {"ok": False, "error": f"unknown persona: {name!r}", "available": sorted(PERSONAS.keys())}
        self._persona = get(name)
        return {
            "ok": True,
            "persona": self._persona.name,
            "description": self._persona.description,
            "preferred_tools": list(self._persona.preferred_tools),
            "tone": self._persona.tone,
        }

    def get_persona(self) -> dict[str, Any]:
        return {
            "persona": self._persona.name,
            "description": self._persona.description,
            "preferred_tools": list(self._persona.preferred_tools),
            "tone": self._persona.tone,
        }

    def _system_message(
        self,
        mode: AgentMode | None = None,
        plan: MissionPlan | None = None,
        selected_tool_names: list[str] | None = None,
        user_text: str | None = None,
    ) -> dict[str, str]:
        # Rama Experimentando: SIN forzado de idioma. No se inyecta la
        # instrucción "Reply ONLY in <lang>" — el LLM responde en el idioma que
        # elija nativamente a partir del mensaje del usuario.
        language_section = ""
        mode_hint = f"\n\n# Current mode\n{mode.system_hint}" if mode else ""
        plan_hint = f"\n\n{plan.prompt_hint()}" if plan and plan.prompt_hint() else ""
        persona_hint = f"\n\n{self._persona.system_hint}" if self._persona.system_hint else ""
        # Accessibility mode (perceptual/motor). Session-level (no cambia por
        # turno) -> va en el bloque ESTABLE junto a persona, cache-friendly. El
        # `system_hint` está vacío para 'normal', así que esto es no-op salvo
        # que el usuario haya activado un modo. Las garantías DURAS (narrar /
        # confirmar / hands-free) las aplican guardas estructurales en runtime,
        # no este texto. Fallback seguro: cualquier error -> sin hint.
        try:
            from .. import accessibility as _a11y
            _a11y_hint = _a11y.get_active_mode().system_hint
        except Exception:
            _a11y_hint = ""
        accessibility_hint = f"\n\n{_a11y_hint}" if _a11y_hint else ""
        # Nota transitoria (un turno) si el usuario acaba de cambiar de modo por
        # voz — el LLM la usa para confirmar el cambio. Va en la cola VARIABLE.
        a11y_switch_note = (f"\n\n{self._a11y_switch_note}"
                            if getattr(self, "_a11y_switch_note", "") else "")
        info_followup_note = (f"\n\n{self._info_followup_note}"
                              if getattr(self, "_info_followup_note", "") else "")
        from ..memory_pkg.experience import format_recall_for_prompt
        from ..mission.explicit_plan import format_for_prompt as _format_explicit_plan
        from ..memory_pkg.project_context import format_for_prompt as _format_project_context
        from ..memory_pkg.project_context import load_context
        project_block = _format_project_context(load_context())
        project_section = f"\n\n{project_block}" if project_block else ""
        recall_hint = format_recall_for_prompt(self._recent_recalls)
        recall_section = f"\n\n{recall_hint}" if recall_hint else ""
        # Perfil de gustos del usuario: párrafo sintetizado
        # de quién es el usuario (apps/música/ritmo observados por el ambient
        # observer), para que Gemma4 personalice. GPG arXiv:2409.13093 (+37%):
        # párrafo NL, no log crudo. build_profile_block CACHEA con TTL (corre por
        # turno; sin caché re-leía 15.7k eventos → ~18ms/turno, rompía el budget).
        # Gate GEMMA4_TASTE_PROFILE. Best-effort: error -> sin perfil.
        profile_section = ""
        if self.behavior is not None:
            try:
                from ..memory_pkg.taste_profile import build_profile_block
                profile_section = build_profile_block(self.behavior)
                # Reflexión por LLM (opt-in GEMMA4_TASTE_LLM_REFLECTION):
                # gustos FINOS inferidos en background. reflection_block sólo LEE el caché
                # (barato); maybe_refresh_async dispara el pase LLM en un thread si venció
                # (NO per-turn). Gate OFF -> ambos no-op. Best-effort.
                from ..memory_pkg.taste_reflection import (
                    reflection_block as _refl_block, maybe_refresh_async as _refl_refresh)
                if profile_section:
                    profile_section += _refl_block(self.behavior)
                _refl_refresh(self.behavior, self.client)
            except Exception:
                pass
        explicit_block = _format_explicit_plan(self._explicit_plan_text)
        explicit_section = f"\n\n{explicit_block}" if explicit_block else ""
        phrase_section = _format_phrase_fires(self._phrase_fires)
        phrase_section = f"\n\n{phrase_section}" if phrase_section else ""
        # Bloque "Tool Schemas EXACT". Patron Daniel Farina (OpenCode-on-Gemma-4):
        # reduce errores de tool selection y argument naming. Opt-out via env var
        # GEMMA4_DISABLE_TOOL_SCHEMAS_HINT por si el dev necesita prompts
        # mas cortos en debug. Cacheado a nivel-instancia para no recompilar
        # el markdown en cada turno (62 tools = ~6 KB de markdown).
        #
        # PERF: si el caller pasa selected_tool_names (el subset que el
        # semantic router eligio para este turn), filtramos el markdown a solo
        # esos tools. De ~46K chars (62 tools full) a ~3-5K (4-6 tools), 10x
        # menos prefill por turno.
        tools_section = self._tool_schemas_hint(selected_tool_names=selected_tool_names)
        # PERF: el system prompt base ahora se filtra por subset: CORE + solo
        # reglas de las tools que el router eligio. Reduce ~7K chars sin
        # perder capacidad (cuando el LLM use la tool, la regla aparecera).
        prompt_base = build_system_prompt(selected_tool_names)
        # Microagents — markdown files con frontmatter que se
        # inyectan al system_prompt cuando user_text matchea sus triggers.
        # Diferencia ortogonal con TOOL_RULES:
        #   TOOL_RULES["X"]: como usar la tool X (regla de uso, viene con
        #     selected_tool_names).
        #   microagent: que SIGNIFICA un concepto / como diagnosticar (conoc.
        #     de dominio, viene con user_text).
        # Cache a nivel-instancia: lo que matchea en un turn persiste para
        # los siguientes (KV cache caliente entre turns relacionados).
        try:
            from ..memory_pkg.microagents import build_microagents_section
            microagents_section, self._cached_microagents = build_microagents_section(
                user_text or "",
                cached=self._cached_microagents,
            )
        except Exception as _exc:
            try:
                self.trace.event(
                    "agent", "silent_fallback",
                    component="microagents",
                    error=f"{type(_exc).__name__}: {_exc}",
                )
            except Exception:
                pass
            microagents_section = ""
        # Skills menu (compact, una linea por skill) + critical
        # block (full body de skills con priority=critical). Cacheado a
        # nivel-instancia: el catalogo skills/ no cambia mid-session.
        if self._cached_skills_menu is None or self._cached_skills_critical is None:
            try:
                from ..tools_pkg.skills_registry import scan_skills, build_menu, build_critical_block
                skills_list = scan_skills()
                self._cached_skills_menu = build_menu(skills_list)
                self._cached_skills_critical = build_critical_block(skills_list)
            except Exception as _exc:
                try:
                    self.trace.event(
                        "agent", "silent_fallback",
                        component="skills_registry",
                        error=f"{type(_exc).__name__}: {_exc}",
                    )
                except Exception:
                    pass
                self._cached_skills_menu = ""
                self._cached_skills_critical = ""
        skills_critical = self._cached_skills_critical or ""
        skills_menu = self._cached_skills_menu or ""
        # Trigger-inject de skills: el 4B NO emite skill_load (0/5 en
        # vivo, 0/6727 prod). Si el pedido matchea semánticamente una skill,
        # inyectamos su receta full para que la SIGA (como microagents/critical),
        # sin depender de que el 4B la cargue. Gated GEMMA4_SKILLS_AUTOINJECT.
        skills_autoinject = ""
        if _skills_autoinject_enabled():
            try:
                from ..tools_pkg.skills_registry import autoinject_skill, scan_skills
                from ..routing import semantic_router as _sr_sk
                if _sr_sk.status().get("model_loaded"):
                    _sk_name, _sk_body = autoinject_skill(
                        user_text or "", scan_skills(), embed_fn=_sr_sk.embed)
                    if _sk_name:
                        skills_autoinject = (
                            f"\n# SKILL ACTIVADA — seguí esta receta paso a paso\n"
                            f"## {_sk_name}\n{_sk_body}\n")
                        self.trace.event("agent", "skill_autoinjected", skill=_sk_name)
            except Exception:
                pass
        # Rama Experimentando: SIN intent-tag forcing (intent_validator removido).
        # El LLM no emite <intent>; el dispatcher no rechaza por mismatch.
        intent_hint = ""
        # LAYOUT cache-friendly (medido):
        # el system prompt diverge al ~28% porque las TOOL_RULES (variables por
        # subset del router) iban temprano -> cambiar de dominio de tools
        # (Spotify->volumen) reprocesaba ~4000 tok (892ms). V2 reordeno:
        # ESTABLE primero, VARIABLE al final. Pero el prefijo comun caia a 33-46%
        # entre turns reales porque las tool_rules y tool_schemas filtrados por
        # subset (variables) seguian en el system.
        #
        # V3: las CORE_TOOL_RULES de los 15 tools mas usados (93.8% Pareto) y los
        # CORE_TOOL_SCHEMAS van en el SYSTEM SIEMPRE (bytes estables turno-a-
        # turno). Las tool-rules y schemas para tools fuera del core van como
        # hint al inicio del USER msg. cache_hit medido en simulacion: 0.19% V2
        # -> 99.85% V3 cuando solo cambia el user.
        # Gates: GEMMA4_PROMPT_LAYOUT_V3=0 vuelve a V2.
        #        GEMMA4_PROMPT_LAYOUT_V2=0 vuelve al orden V1 (legacy).
        import os as _os_layout
        _v3_on = _os_layout.environ.get("GEMMA4_PROMPT_LAYOUT_V3", "1").strip().lower() \
                 not in {"0", "false", "no", "off"}
        _v2_on = _os_layout.environ.get("GEMMA4_PROMPT_LAYOUT_V2", "1").strip().lower() \
                 not in {"0", "false", "no", "off"}
        if _v3_on:
            from .agent_prompt import (
                build_core_only,
                build_core_tool_rules_stable,
            )
            core_stable = build_core_only()
            # Split (FunctionGemma router): las reglas de uso de tools son REDUNDANTES —
            # FG hace el ruteo y el modelo que habla solo conversa/narra. Sacarlas baja el
            # prompt ~1150 tok (MEDIDO 2026-06-17). Sin FG van SIEMPRE (15 tools fijos,
            # bytes estables turno-a-turno para el cache-hit del prefijo; las extras se
            # inyectan al user msg desde _decide_turn / _execute_turn).
            if _fg_router_on():
                stable_a = f"{core_stable}\n\n"
            else:
                core_tool_rules = build_core_tool_rules_stable()
                stable_a = (f"{core_stable}\n\n# Core tool usage rules\n"
                            f"{core_tool_rules}\n\n")
            stable_b = f"{persona_hint}{accessibility_hint}{skills_critical}{skills_menu}"
            # VARIABLE al final: mode-hint, tool-schemas (filtrados por subset
            # por ahora), project/plan/recall/phrase/microagents/intent/memoria.
            variable = (f"{language_section}{mode_hint}{a11y_switch_note}{info_followup_note}{tools_section}"
                        f"{project_section}{profile_section}{plan_hint}{explicit_section}"
                        f"{recall_section}{phrase_section}{microagents_section}"
                        f"{skills_autoinject}{intent_hint}\n\n# Persistent memory\n"
                        f"{self.memory.prompt_summary_for(user_text)}")
            return {"role": "system", "content": stable_a + stable_b + variable}
        if _v2_on:
            from .agent_prompt import build_core_only, build_tool_rules_tail
            core_stable = build_core_only()
            # Split FG: reglas de uso de tools redundantes (FG rutea) -> fuera bajo FG.
            tool_rules_tail = "" if _fg_router_on() else build_tool_rules_tail(selected_tool_names)
            tool_rules_section = f"\n\n{tool_rules_tail}" if tool_rules_tail else ""
            stable = f"{core_stable}{persona_hint}{accessibility_hint}{skills_critical}{skills_menu}"
            variable = (f"{language_section}{mode_hint}{a11y_switch_note}{info_followup_note}{tool_rules_section}{tools_section}"
                        f"{project_section}{profile_section}{plan_hint}{explicit_section}"
                        f"{recall_section}{phrase_section}{microagents_section}"
                        f"{skills_autoinject}{intent_hint}\n\n# Persistent memory\n"
                        f"{self.memory.prompt_summary_for(user_text)}")
            return {"role": "system", "content": stable + variable}
        return {
            "role": "system",
            "content": f"{prompt_base}{language_section}{mode_hint}{a11y_switch_note}{info_followup_note}{tools_section}{persona_hint}{accessibility_hint}{project_section}{profile_section}{plan_hint}{explicit_section}{recall_section}{phrase_section}{microagents_section}{skills_autoinject}{skills_critical}{skills_menu}{intent_hint}\n\n# Persistent memory\n{self.memory.prompt_summary_for(user_text)}",
        }

    def _tool_schemas_hint(self, selected_tool_names: list[str] | None = None) -> str:
        """Construye el bloque "Tool Schemas EXACT" una sola vez por agent.

        Mode seleccionado por el context_size del perfil activo:
          - ctx >= 32K  -> full (~11.6K tokens) — best argument fidelity.
          - ctx >= 16K  -> compact (~5.9K tokens) — descripciones cortas.
          - ctx <  16K  -> off (no hint; el catalogo nativo de tools del
                          schema en --jinja sigue siendo el camino).
        Override via GEMMA4_TOOL_SCHEMAS_HINT_MODE = full|compact|off|auto.
        Cache a nivel-instancia porque los schemas son estaticos.
        """
        import os as _os
        # Split (FunctionGemma router): el E2B NO decide tools — lo hace FunctionGemma. Por eso
        # NO necesita los schemas en el prompt. Suprimirlos baja el prompt ~4800->~1.5-2k tokens
        # (menos KV+compute, prefill más rápido, y menos "Context Rot" -> mejor calidad). El E2B
        # sólo conversa y narra resultados de tools, lo cual no requiere los schemas. Validado en
        # la composición vram4_lean (ctx 6144, FG on): persona/idioma/grounding OK sin schemas.
        if _fg_router_on():
            return ""
        env_mode = (_os.environ.get("GEMMA4_TOOL_SCHEMAS_HINT_MODE") or "auto").strip().lower()
        # legacy opt-out kept for backward compat
        legacy_off = (_os.environ.get("GEMMA4_DISABLE_TOOL_SCHEMAS_HINT") or "").strip().lower()
        if legacy_off in {"1", "true", "yes", "on"}:
            env_mode = "off"
        if env_mode == "off":
            return ""
        if env_mode not in {"full", "compact", "auto"}:
            env_mode = "auto"
        if env_mode == "auto":
            ctx = int(self.config.context_size or 0)
            # full: solo en perfiles con ctx >=32K (performance). El hint
            # full es ~11.6K tokens, ~35% de un context 32K — aceptable.
            # compact: ~5.9K tokens. Activo en ctx >=12K (balanced_8gb usa
            # 12K, no 16K, por VRAM tight) para que
            # queden >=6K tokens libres para conversacion + memoria.
            # off: ctx <12K (balanced 8K, light 4K) — el catalogo nativo
            # de tools via --jinja sigue siendo el camino sin overhead.
            if ctx >= 32768:
                mode = "full"
            elif ctx >= 12288:
                mode = "compact"
            else:
                return ""
        else:
            mode = env_mode

        # PERF: si el caller paso selected_tool_names (lista explicita, aunque
        # sea vacia), respetamos el contrato — no inyectamos schemas que el
        # router decidio no necesitar. Esto evita el bug de smalltalk metiendo
        # ~46KB / 11.6K tokens de schemas en cada turn sin necesidad.
        # `None` significa "no subset path requested" → comportamiento legacy
        # (full catalogo). Lista vacia `[]` significa "smalltalk / no tools".
        if selected_tool_names is not None:
            if not selected_tool_names:
                # Smalltalk / no tools necesarias: 0 schemas, 0 tokens.
                return ""
            subset_key = ",".join(sorted(set(selected_tool_names)))
            cache_key = f"_cached_tool_schemas_md_{mode}_{subset_key}"
            cached = getattr(self, cache_key, None)
            if cached is None:
                try:
                    from ..tools_pkg.tools import COMPOUND_TOOL_SCHEMAS, compile_tools_to_markdown_exact
                    wanted = set(selected_tool_names)
                    subset_schemas = [
                        s for s in COMPOUND_TOOL_SCHEMAS
                        if isinstance(s, dict)
                        and isinstance(s.get("function"), dict)
                        and s["function"].get("name") in wanted
                    ]
                    if subset_schemas:
                        cached = compile_tools_to_markdown_exact(
                            schemas=subset_schemas,
                            compact=(mode == "compact"),
                        )
                    else:
                        # Subset solicitado pero no matchea ningun schema
                        # (router devolvio nombres invalidos). No inyectar
                        # full por defensa — log y devolver vacio.
                        logger.warning("tool_schemas_hint: subset %s no matchea ningun schema; devolviendo vacio",
                                       sorted(wanted))
                        cached = ""
                except Exception as _exc:
                    try:
                        self.trace.event(
                            "agent", "silent_fallback",
                            component="tool_schemas_hint_subset",
                            error=f"{type(_exc).__name__}: {_exc}",
                        )
                    except Exception:
                        pass
                    cached = ""
                setattr(self, cache_key, cached)
            return f"\n\n{cached}" if cached else ""

        # Sin subset (caller paso None explicito): comportamiento legacy.
        cache_key = f"_cached_tool_schemas_md_{mode}"
        cached = getattr(self, cache_key, None)
        if cached is None:
            try:
                from ..tools_pkg.tools import compile_tools_to_markdown_exact
                cached = compile_tools_to_markdown_exact(compact=(mode == "compact"))
            except Exception as _exc:
                try:
                    self.trace.event(
                        "agent", "silent_fallback",
                        component="tool_schemas_hint_full",
                        error=f"{type(_exc).__name__}: {_exc}",
                    )
                except Exception:
                    pass
                cached = ""
            setattr(self, cache_key, cached)
        return f"\n\n{cached}" if cached else ""

    def _messages(
        self,
        mode: AgentMode | None = None,
        plan: MissionPlan | None = None,
        selected_tool_names: list[str] | None = None,
        user_text: str | None = None,
        route_context: bool = False,
    ) -> list[dict[str, Any]]:
        history = self._history_for_turn(user_text) if route_context else self.history
        # Camino C: si LAYOUT_V3 esta activo y hay tools FUERA del
        # core en el subset, inyectar sus rules como prefijo del ultimo user msg
        # (NO al system, para no romper el cache). El system queda byte-a-byte
        # estable entre turnos -> prefix-cache real ~99% turn-a-turn.
        import os as _os_v3
        if (_os_v3.environ.get("GEMMA4_PROMPT_LAYOUT_V3", "1").strip().lower()
                not in {"0", "false", "no", "off"}
                and selected_tool_names and history):
            try:
                from .agent_prompt import build_tool_rules_extras_for_user_msg
                extras = build_tool_rules_extras_for_user_msg(selected_tool_names)
                if extras:
                    # Localizar el ULTIMO user msg en history (no clonar history
                    # — copia ligera del item modificado para no mutar el estado
                    # persistente del agente).
                    history = list(history)
                    for i in range(len(history) - 1, -1, -1):
                        m = history[i]
                        if m.get("role") == "user":
                            content = m.get("content")
                            if isinstance(content, str):
                                history[i] = {**m, "content": extras + content}
                            # Si el content es lista (multimodal), prefijar como
                            # primer text part. NO tocar imagenes.
                            elif isinstance(content, list):
                                new_content = [
                                    {"type": "text", "text": extras},
                                    *content,
                                ]
                                history[i] = {**m, "content": new_content}
                            break
            except Exception:
                # Si algo falla, dejar history sin modificar (fallback seguro).
                pass
        msgs = [
            self._system_message(
                mode, plan,
                selected_tool_names=selected_tool_names,
                user_text=user_text,
            ),
            *history,
        ]
        # PREFIX-REWARM (latencia): stash del system de ESTE turno + flag de
        # thinking del modo, para que _prefix_rewarm_async pueda re-calentar el
        # slot del server en el idle post-turno. Los pases utilitarios cortos
        # (_llm_action_reply, repairs) usan un system propio de ~100 tok que
        # REEMPLAZA el KV del slot único (--parallel 1): el turno siguiente
        # matchea ~4 tokens y re-prefilea ~6K (~1.1s, medido en vivo con
        # _probe_cache_divergence). El rewarm repone el prefijo grande fuera
        # del camino crítico. Best-effort.
        try:
            _sys_c = msgs[0].get("content")
            if isinstance(_sys_c, str) and _sys_c:
                self._rewarm_system = _sys_c
                self._rewarm_thinking = (
                    bool(mode.enable_thinking) if mode is not None else True)
        except Exception:
            pass
        return msgs

    def _history_for_turn(self, user_text: str | None) -> list[dict[str, Any]]:
        """Router de contexto (inv 4): la mayoría de los comandos de voz son
        atómicos -> no mandar historial previo recorta el tail que SIEMPRE se
        reprocesa (medido: el prefix-cache de b9090 SÍ funciona para Gemma 4 E4B,
        pero el tail variable no se cachea). Conservador: sólo droppea el
        historial PREVIO cuando el turno es claramente autocontenido; siempre
        conserva el turno actual (self.history[-1]).

        SÓLO se llama en la PRIMERA llamada al LLM del turno (route_context=True,
        len(events)==0). En ese punto self.history sólo contiene user/assistant
        (_compact_completed_history corrió al inicio del turno y droppea
        tool/tool_calls), y hist[-1] es el turno actual recién appendeado. NO se
        usa dentro del loop de tools (ahí history acumula call/result y slicear
        rompería el pairing del chat template de Gemma 4)."""
        hist = self.history
        if not hist or len(hist) < 2:
            return hist
        # Guardia dura: si hay algún tool-call/result en el historial, NO tocar
        # (no debería pasar en la 1ª llamada, pero protege ante reentradas).
        if any(m.get("role") == "tool" or m.get("tool_calls") for m in hist):
            return hist
        try:
            from ..routing.context_router import needs_history, select_history
            prior, current = hist[:-1], hist[-1:]
            mode = needs_history(user_text or "", has_history=bool(prior))
            kept_prior = select_history(prior, mode)
            if len(kept_prior) != len(prior):
                self.trace.event(
                    self.trace.new_turn_id(), "context_router",
                    mode=mode, prior_msgs=len(prior), kept=len(kept_prior))
            return [*kept_prior, *current]
        except Exception:
            return hist

    def run_text(
        self,
        text: str,
        images: list[Path] | None = None,
        audios: list[Path] | None = None,
        progress: ProgressCallback | None = None,
        *,
        tts_sink: "Callable[[str], int | None] | None" = None,
    ) -> AgentReply:
        content = user_content(text, images=images, audios=audios)
        return self.run_content(content, progress=progress, tts_sink=tts_sink)


    def _decide_turn(self, content: str | list[dict[str, Any]], progress: ProgressCallback | None = None) -> TurnDecision:
        """Decide phase of a turn.

        Runs router + abstain + planner + subset + pending_intent +
        splitter + multi-intent carry. Returns a TurnDecision; if
        `early_reply` is set, run_content propagates it without
        executing the LLM (caso jarvis-pending handshake, multi-intent
        re-dispatch, reply-message shortcut, explicit-plan only).
        """
        self._turn_counter += 1
        turn_id = self.trace.new_turn_id()
        _decide_t0 = time.perf_counter()
        _decide_last = _decide_t0

        def _mark_decide_phase(phase: str, **payload: Any) -> None:
            nonlocal _decide_last
            now = time.perf_counter()
            try:
                self.trace.event(
                    turn_id,
                    "decide_phase",
                    phase=phase,
                    delta_ms=round((now - _decide_last) * 1000.0, 3),
                    since_start_ms=round((now - _decide_t0) * 1000.0, 3),
                    **payload,
                )
            except Exception:
                pass
            _decide_last = now
        # Resetear el presupuesto de acciones físicas GUI al EMPEZAR un turno
        # top-level (no por cláusula — las cláusulas de un multi-intent comparten
        # el presupuesto del turno). Acota cuántos clicks/types a ciegas puede
        # encadenar el agente (anti pop-up/visual injection).
        if not getattr(self, "_splitting", False):
            try:
                from .. import gui_safety
                gui_safety.reset_action_budget()
                # anchor-binding: fijar el objetivo del turno para detectar
                # clicks a bait de pop-up no relacionado.
                try:
                    _goal_txt = content if isinstance(content, str) else ""
                    if not _goal_txt and isinstance(content, list):
                        _goal_txt = " ".join(
                            str(p.get("text", "")) for p in content
                            if isinstance(p, dict) and p.get("type") == "text")
                    gui_safety.set_turn_goal(_goal_txt)
                    # Turn language uses the same selector as the prompt and
                    # final reply repair, so router-adjacent state cannot drift.
                    try:
                        self._turn_lang = _reply_lang(_goal_txt) if _goal_txt else "es"
                    except Exception:
                        self._turn_lang = "es"
                except Exception:
                    pass
            except Exception:
                pass
        _mark_decide_phase("early_gui_lang")
        # Reset de la nota transitoria de cambio-de-modo (un turno). Va ANTES de
        # cualquier short-circuit para que no filtre de un turno al siguiente.
        self._a11y_switch_note = ""
        self._info_followup_note = ""
        self._info_followup_prefetch_query = ""
        self._a11y_continue_count = 0  # re-prompts de accesibilidad usados este turno
        # Si el turno anterior ofreció automatizar una rutina y
        # el usuario responde sí/no, resolverlo ACÁ (antes del LLM) — es un
        # handshake determinista, no hace falta inferencia. Short-circuit del turno.
        _jarvis_reply = self._handle_pending_suggestion(content)
        if _jarvis_reply is not None:
            return TurnDecision(early_reply=_jarvis_reply)
        _mark_decide_phase("pending_suggestion")
        # PERFIL DE GUSTOS — privacidad inspectable/borrable.
        # "¿qué sabés de mí?" / "olvidate de mis datos" tienen respuesta DETERMINISTA
        # (mostrar/borrar el perfil). MEDIDO: el router las clasifica como acción y el
        # 4B devuelve reply vacío → short-circuit. Detección por EMBEDDINGS (no
        # keywords). forget PIDE CONFIRMACIÓN (irreversible). Resuelto ANTES del LLM.
        _profile_reply = self._handle_profile_intent(content)
        if _profile_reply is not None:
            return TurnDecision(early_reply=_profile_reply)
        _mark_decide_phase("profile_intent")
        # ACCESIBILIDAD: si el usuario PIDE cambiar de modo de accesibilidad
        # ("activá modo no vidente", "no puedo usar las manos", "volvé a normal"),
        # lo detectamos por EMBEDDINGS multilingües (no keywords) y lo aplicamos/
        # persistimos ACÁ, antes de elegir tools. NO short-circuiteamos con una
        # respuesta enlatada: dejamos seguir el turno para que el LLM confirme el
        # cambio con sus palabras, ya con el system_hint del nuevo modo activo.
        # Fallback seguro: si el encoder está caído, maybe_switch_mode -> None.
        if isinstance(content, str) and content.strip():
            try:
                from .. import accessibility_voice as _a11y_voice
                _switched = _a11y_voice.maybe_switch_mode(content)
                if _switched is not None:
                    self._a11y_switch_note = (
                        f"# Cambio de modo de accesibilidad\n"
                        f"El usuario acaba de pedir cambiar al modo "
                        f"«{_switched.display_name}». Ya quedó ACTIVADO y "
                        f"persistido. Confirmáselo en UNA frase breve, con tus "
                        f"palabras y en su idioma, y seguí asistiéndolo en ese "
                        f"modo. No expliques la implementación."
                    )
                    try:
                        self.trace.event(turn_id, "a11y_mode_switch",
                                         mode=_switched.name)
                    except Exception:
                        pass
            except Exception:
                pass
        _mark_decide_phase("a11y_switch_check")
        # COMPUTER-USE ES UNA TOOL (pedido de RED): operar dentro
        # de una app abierta ya NO es un short-circuit pre-LLM que secuestraba turnos
        # (causaba: "abre steam"->enfoca/minimiza, WhatsApp->escribe en la caja
        # equivocada, "router no ofrece tools"). Ahora `computer_use(goal=...)` es una
        # tool más del registry: el router la ofrece y el LLM la llama como cualquier
        # otra, con sus parámetros. Su impl (tools.t_computer_use) corre el plan
        # executor internamente. Sin gate frágil, sin secuestro — unificado.
        # Rama Experimentando: SIN short-circuits deterministas pre-LLM.
        # Removidos aritmetica/calc/app-action/deterministic-reply (parsing
        # por command_splitter que disparaba tools SIN que el LLM decida).
        # El LLM nativo decide y llama las tools del subset semantico.
        # Allow ONE forced tool-call retry per user turn (reset here; consumed
        # in the agent loop when a domain tool was expected but none was called).
        _mark_decide_phase("reply_net_check")
        _mark_decide_phase("pre_llm_shortcuts")
        self._forced_tool_retry_done = False
        self._det_nets_tried = False  # redes deterministas (reply/email/nav) por turno
        self._fg_router_done = False  # FunctionGemma router: 1 decisión de tool por turno
        mode = choose_mode(content, self.config.agent_mode, self.config.max_tokens)
        plan = plan_mission(content)
        _mark_decide_phase("mode_plan", mode=mode.name, steps=len(plan.steps))
        # turn_id ya se generó arriba (antes del macro de navegación-en-app).
        # Router mode (lazy vision): pick the per-turn router preset. vision
        # only when this turn actually has an image (mode==vision_action) — so
        # text/voice turns use the cache-reuse-enabled text preset (fast). None
        # when not in router mode -> client uses the configured model.
        self._router_model = None
        try:
            # SERVER-driven resolution: probe /v1/models so this is correct in
            # ANY process (launcher, standalone UI server, smoke tests) — the
            # manager singleton isn't shared across processes, but the running
            # server is ground truth. Falls back to manager state if the probe
            # can't run (e.g. server not up yet during boot warmup).
            from ..infra.llama_server import resolve_turn_model, get_shared_manager
            self._router_model = resolve_turn_model(
                has_image=(mode.name == "vision_action"))
            if self._router_model is None:
                mgr = get_shared_manager()
                if mgr.is_router_mode():
                    self._router_model = mgr.router_model_for(
                        has_image=(mode.name == "vision_action"))
        except Exception:
            self._router_model = None
        # WATCHDOG inv 6.1: prevenir el OOM CUDA que deja el server zombie
        # (#13085, causa raiz del proxy zombie). Politica por nivel:
        #   - critical  (free < 400 MiB)  -> BLOQUEAR el turno de vision: avisar
        #                                     al user honesto, no intentarlo.
        #                                     El mmproj no cabe; cargar = OOM.
        #   - degrade   (400-800 MiB)     -> seguir, pero recyclar el server
        #                                     para liberar memoria fragmentada
        #                                     (descarga mmproj + reload limpio).
        #   - warn/ok                     -> seguir normal, solo trace.
        # Esto cambia el comportamiento previo de "fail-loud sin bloquear" a
        # "prevenir el OOM antes que reaccionar tras zombie" (inv 6.1 punto 1:
        # 'detectar antes con NVML es la unica estrategia que evita el reload').
        if (mode.name == "vision_action"
                and getattr(self, "vram_watchdog", None) is not None):
            import logging as _vram_logging
            _vram_log = _vram_logging.getLogger(__name__)
            try:
                _vs = self.vram_watchdog.snapshot()
                if _vs.available and _vs.level == "critical":
                    try:
                        self.trace.event(
                            turn_id, "vram_pressure_block",
                            level=_vs.level, free_mib=_vs.free_mib,
                            used_mib=_vs.used_mib, context="vision_turn",
                            action="blocked")
                    except Exception:
                        pass
                    _vram_log.warning(
                        "VRAM critical (free=%.0fMiB), bloqueando turno de "
                        "vision para evitar OOM zombie (#13085)", _vs.free_mib)
                    return TurnDecision(early_reply=AgentReply(
                        content=(
                            "Necesito ver la pantalla pero la VRAM esta muy "
                            "ocupada ahora mismo (queda poco libre). Liberala "
                            "y volve a pedirme."),
                        tool_events=[],
                        mission={"mission_status": "FAILED",
                                 "reason": "vram_critical_for_vision",
                                 "free_mib": int(_vs.free_mib)},
                    ))
                if _vs.available and _vs.level == "degrade":
                    # Reciclar el server: free + recarga limpia + reset del
                    # counter mmproj. Best-effort: si falla, seguimos con el
                    # warning (al menos lo intentamos antes del OOM).
                    try:
                        from ..infra.llama_server import get_shared_manager
                        mgr = get_shared_manager()
                        recycled = mgr.recycle_for_vision_leak()
                    except Exception as exc:
                        recycled = False
                        _vram_log.warning("vram-degrade recycle failed: %s", exc)
                    try:
                        self.trace.event(
                            turn_id, "vram_pressure_recycle",
                            level=_vs.level, free_mib=_vs.free_mib,
                            used_mib=_vs.used_mib, context="vision_turn",
                            recycled=recycled)
                    except Exception:
                        pass
                    _vram_log.warning(
                        "VRAM degrade (free=%.0fMiB) before vision turn; "
                        "recycled=%s", _vs.free_mib, recycled)
                elif _vs.available and not self.vram_watchdog.vision_safe():
                    # warn: solo log/trace, no degradar todavia.
                    _vram_log.warning(
                        "VRAM watchdog: turno de VISIÓN con libre=%.0fMiB "
                        "(nivel=%s); margen ajustado para mmproj ~946MiB",
                        _vs.free_mib, _vs.level)
                    try:
                        self.trace.event(
                            turn_id, "vram_pressure", level=_vs.level,
                            free_mib=_vs.free_mib, used_mib=_vs.used_mib,
                            context="vision_turn")
                    except Exception:
                        pass
            except Exception:
                pass
        # Persona is currently visible only via tool_subset.persona,
        # which isn't emitted on every turn. Emit one canonical event per turn
        # so the usage report can quantify which personas actually run.
        try:
            self.trace.event(
                turn_id, "persona_active",
                persona=self._persona.name,
                tone=self._persona.tone,
            )
        except Exception:
            pass
        # Phrase-triggered routines: check the user's plain text against
        # saved on_phrase routines BEFORE the LLM call. Each matching routine
        # runs its steps once; the results are inlined into the system prompt
        # so Gemma can confirm naturally without re-running the tools.
        self._phrase_fires = []
        raw_text_early = _extract_user_text(content)
        # Track current user text for the fallback-streak detector.
        self._current_user_text = (raw_text_early or "").strip().lower()
        # Texto ORIGINAL (sin lowercase) para regenerar replies con el LLM
        # (knowledge_reply): el casing importa para nombres propios.
        self._current_user_text_raw = (raw_text_early or "").strip()
        # Plumbear el texto del turno al ToolRegistry: las tools que necesitan
        # GROUNDING DE PROCEDENCIA (p.ej. whatsapp: ¿el user DICTÓ este número, o
        # el 4B lo alucinó?) lo leen de ahí. Sin esto el registry no ve el mensaje
        # original. Best-effort: si self.tools aún no existe, no rompe.
        try:
            self.tools._current_user_text = self._current_user_text
        except Exception:
            pass
        # ITEM 4: si el turno es DEÍCTICO (multilingüe por embeddings) y el entity
        # ring tiene un identificador reciente, inyectar el referente LITERAL al
        # final del historial (el 4B sufre lost-in-the-middle: el referente debe ir
        # junto al pronombre). Gated GEMMA4_DEICTIC, best-effort, fallback seguro.
        try:
            ring = getattr(self, "_entity_ring", None)
            if ring is not None and not ring.is_empty() and raw_text_early:
                from ..routing.deictic_detector import (
                    needs_deictic_context, deictic_context_block)
                if needs_deictic_context(raw_text_early):
                    block = deictic_context_block(ring)
                    if block:
                        self.history.append({"role": "user", "content": block})
                        try:
                            self.trace.event(turn_id, "deictic_context_injected",
                                             entity=ring.most_recent())
                        except Exception:
                            pass
        except Exception:
            pass
        # Log which microagents matched this turn (independent of
        # the cache-merge step inside _system_message). Without this it
        # was unobservable in traces.jsonl.
        if raw_text_early:
            try:
                from ..memory_pkg.microagents import (
                    load_microagents, select_microagents, _default_embed_fn)
                # R3.3: pasar el encoder para que el trace refleje la selección
                # SEMÁNTICA real (no solo el path léxico word-boundary).
                _matched_ma = select_microagents(
                    raw_text_early, load_microagents(),
                    embed_fn=_default_embed_fn())
                if _matched_ma:
                    self.trace.event(
                        turn_id, "microagent_matched",
                        names=[m.name for m in _matched_ma],
                        count=len(_matched_ma),
                    )
            except Exception:
                pass
        if raw_text_early:
            try:
                from ..domain_tools import (_looks_destructive,
                                            active_phrase_triggers)
                folded_input = _fold_match(raw_text_early)
                # Per-step timeout so a hung tool never blocks the whole turn.
                # Configurable via env; default 30s per step.
                import os as _os
                step_timeout = float(_os.environ.get("GEMMA4_PHRASE_STEP_TIMEOUT_S") or 30)
                # "Frase sola": el usuario dijo esencialmente la palabra-frase
                # y nada más (ej. "tiempo", "tiempo."). En ese caso ejecutamos
                # la rutina y cortamos el turno sin pasar por el LLM. Si la
                # frase aparece DENTRO de una oración más larga, el turno sigue
                # normal (el LLM responde con contexto).
                _input_core = _strip_for_phrase_only(folded_input)
                for routine in active_phrase_triggers(self.state):
                    needle = _fold_match(str(routine.get("phrase") or ""))
                    if not needle or needle not in folded_input:
                        continue
                    phrase_only = _strip_for_phrase_only(needle) == _input_core
                    # Extra safety for destructive routines: do NOT fire if the
                    # user message looks like a question or hypothetical that
                    # merely *mentions* the phrase. We check the steps for a
                    # destructive command token; if found, require the message
                    # to NOT contain a question mark and NOT start with a
                    # hypothetical opener ("que pasa si", "what if", "como se",
                    # "how do i", etc).
                    steps_for_routine = routine.get("steps") or []
                    is_destructive = False
                    for step in steps_for_routine:
                        if isinstance(step, dict):
                            cmd = (step.get("args") or {}).get("command", "") if isinstance(step.get("args"), dict) else ""
                            if cmd:
                                hit, _ = _looks_destructive(str(cmd))
                                if hit:
                                    is_destructive = True
                                    break
                    if is_destructive:
                        if "?" in raw_text_early:
                            self.trace.event(turn_id, "phrase_trigger_skipped_destructive_question",
                                             routine_id=routine.get("id"), phrase=routine.get("phrase"))
                            continue
                        hypotheticals = ("que pasa si", "que ocurre si", "que sucede si",
                                          "y si digo", "y si pongo", "y si escribo",
                                          "what if", "what happens if",
                                          "how do i", "how would i",
                                          "is it ok if", "is it safe to")
                        starts_hypothetical = any(folded_input.startswith(h) for h in hypotheticals)
                        if starts_hypothetical:
                            self.trace.event(turn_id, "phrase_trigger_skipped_destructive_hypothetical",
                                             routine_id=routine.get("id"), phrase=routine.get("phrase"))
                            continue
                    step_results: list[dict[str, Any]] = []
                    for step in routine.get("steps") or []:
                        if not isinstance(step, dict):
                            step_results.append({"ok": False, "error": "invalid step"})
                            continue
                        tname = str(step.get("tool") or "").strip()
                        targs = step.get("args") if isinstance(step.get("args"), dict) else {}
                        if not tname or tname == "routine":
                            step_results.append({"ok": False, "error": "invalid or recursive tool", "tool": tname})
                            continue
                        step_result = _run_with_timeout(self.tools.execute, tname, targs, timeout_s=step_timeout)
                        if step_result.get("_timed_out"):
                            step_results.append({"tool": tname, "ok": False, "error": f"step timed out after {step_timeout}s", "timed_out": True})
                            self.trace.event(turn_id, "phrase_trigger_step_timeout", routine_id=routine.get("id"), tool=tname, timeout_s=step_timeout)
                        elif step_result.get("_error"):
                            step_results.append({"tool": tname, "ok": False, "error": f"step raised: {step_result['_error']}", "exception": True})
                            self.trace.event(turn_id, "phrase_trigger_step_exception", routine_id=routine.get("id"), tool=tname, error=step_result["_error"])
                        else:
                            result = step_result.get("result") or {}
                            step_results.append({"tool": tname, "ok": bool(result.get("ok")), "error": result.get("error"), "status": result.get("status")})
                    fire = {
                        "routine_id": routine.get("id"),
                        "label": routine.get("label"),
                        "phrase": routine.get("phrase"),
                        "results": step_results,
                        "phrase_only": phrase_only,
                    }
                    self._phrase_fires.append(fire)
                    self.trace.event(turn_id, "phrase_trigger_fired",
                                     routine_id=routine.get("id"),
                                     phrase=routine.get("phrase"),
                                     step_count=len(step_results),
                                     ok_count=sum(1 for r in step_results if r.get("ok")),
                                     timeouts=sum(1 for r in step_results if r.get("timed_out")))
            except Exception as exc:
                self.trace.event(turn_id, "phrase_trigger_error", error=str(exc))
        _mark_decide_phase("phrase_triggers", fires=len(self._phrase_fires or []))

        # Frase-sola → ejecutar y CORTAR el turno sin LLM. Cuando el usuario
        # dijo solo la palabra-frase (no una oración que la contiene), la
        # rutina ya corrió arriba; respondemos con un mensaje fijo y nos
        # ahorramos la llamada al modelo (latencia ~0 + sin contexto inyectado).
        _phrase_only_fires = [f for f in self._phrase_fires if f.get("phrase_only")]
        if _phrase_only_fires:
            reply = _format_phrase_only_reply(_phrase_only_fires)
            self.trace.event(turn_id, "phrase_trigger_shortcircuit",
                             fires=len(_phrase_only_fires),
                             ok=sum(1 for f in _phrase_only_fires if _phrase_fire_ok(f)),
                             failed=sum(1 for f in _phrase_only_fires if not _phrase_fire_ok(f)),
                             labels=[f.get("label") or f.get("phrase") for f in _phrase_only_fires])
            # Registramos el turno en el historial como cualquier otro para que
            # una continuación ("subelo más") tenga contexto coherente.
            self._compact_completed_history()
            self.history.append({"role": "user", "content": _compact_live_content(content)})
            self.history.append({"role": "assistant", "content": reply})
            # Mismos invariantes de cierre de turno que el camino normal: señal
            # 'final' a la UI/voz, timestamp para el TTL de inherit-tools, y
            # limpiar las tools heredadas (este turno no ejecutó tools del LLM).
            _progress(progress, "final", tools=0, mission=None)
            self._last_turn_ts = time.time()
            self._remember_executed_tools([])
            return TurnDecision(early_reply=AgentReply(content=reply, tool_events=[], mission=None))

        # Semantic memory: recall similar past turns. Hint-only, never blocks.
        self._recent_recalls = []
        raw_text = raw_text_early
        try:
            from ..routing import semantic_router as _semantic_router
            if raw_text and len(raw_text.split()) >= 2:
                # Anti-degradation: tighter than the permissive
                # default (1.2 ≈ cos 0.4). 0.9 ≈ cos 0.55 — only inject a past
                # turn that is genuinely similar. A weak match just adds prompt
                # tokens (latency) and can mislead with loosely-related
                # precedent. k stays 3 but most turns now recall 0–2.
                _semantic_ready = bool(_semantic_router.status().get("model_loaded"))
                if not _semantic_ready and not _experience_cold_load_enabled():
                    self.trace.event(
                        turn_id,
                        "experience_recall_skipped",
                        reason="semantic_encoder_cold",
                    )
                else:
                    self._recent_recalls = self.experience.recall(
                        raw_text, embed_fn=_semantic_router.embed, k=3, max_distance=0.9)
                if self._recent_recalls:
                    self.trace.event(turn_id, "experience_recall",
                                     query=raw_text[:200],
                                     count=len(self._recent_recalls),
                                     ids=[r["id"] for r in self._recent_recalls],
                                     distances=[r["distance"] for r in self._recent_recalls])
        except Exception as exc:
            self.trace.event(turn_id, "experience_recall_failed", error=str(exc))
        _mark_decide_phase(
            "experience_recall",
            recalls=len(getattr(self, "_recent_recalls", []) or []),
        )

        # Explicit Planner -> Executor (Goose-style). Only spend the extra LLM
        # call when the request is multi-step or the user asked for a plan.
        self._explicit_plan_text = ""
        self._explicit_plan_steps = []
        self._explicit_plan_status = {}
        # PERF: el explicit planner es una segunda llamada al LLM (45s timeout)
        # que se disparaba por heuristica (should_plan). Para queries simples
        # ("abre Steam") era overhead innecesario. Lo hacemos OPT-IN: default
        # OFF, se activa con GEMMA4_AGENT_EXPLICIT_PLAN=true. La capacidad
        # multi-step del LLM se preserva porque el sistema sigue usando el
        # MissionPlan implicito (plan_mission) + multi-turn tool calls.
        import os as _os_plan
        explicit_plan_enabled = (_os_plan.environ.get("GEMMA4_AGENT_EXPLICIT_PLAN") or "").strip().lower() in {"1", "true", "yes", "on"}
        if explicit_plan_enabled:
            try:
                from ..mission.explicit_plan import generate_plan, should_plan
                if raw_text and should_plan(raw_text, len(plan.steps)):
                    self.trace.event(turn_id, "explicit_plan_start", reason="multi_step")
                    result = generate_plan(
                        raw_text,
                        chat_fn=lambda msgs: self.client.chat(msgs, tools=None, enable_thinking=False, parallel_tool_calls=False, max_tokens=350, timeout_s=45.0),
                    )
                    if result.get("ok") and result.get("plan"):
                        self._explicit_plan_text = str(result["plan"])
                        self._explicit_plan_steps = list(result.get("steps") or [])
                        self._explicit_plan_status = {"state": "ready", "step_count": len(self._explicit_plan_steps)}
                        self.trace.event(turn_id, "explicit_plan_ready",
                                         step_count=len(self._explicit_plan_steps),
                                         plan_chars=len(self._explicit_plan_text))
                    elif result.get("skipped"):
                        self._explicit_plan_status = {"state": "skipped", "reason": "model_said_no_plan"}
                        self.trace.event(turn_id, "explicit_plan_skipped", reason="model_said_no_plan")
                    elif not result.get("ok"):
                        self._explicit_plan_status = {"state": "failed", "error": result.get("error")}
                        self.trace.event(turn_id, "explicit_plan_failed", error=result.get("error"))
            except Exception as exc:
                self._explicit_plan_status = {"state": "error", "error": str(exc)}
                self.trace.event(turn_id, "explicit_plan_error", error=str(exc))
        else:
            self._explicit_plan_status = {"state": "disabled", "reason": "env_var_off"}
        _mark_decide_phase(
            "explicit_plan",
            state=(self._explicit_plan_status or {}).get("state"),
        )
        _progress(
            progress,
            "start",
            mode=mode.name,
            steps=len(plan.steps),
            thinking=mode.enable_thinking,
            max_turns=self.config.max_agent_turns,
        )
        self.trace.event(
            turn_id,
            "request_start",
            mode=mode.name,
            content=summarize_content(content),
            mission_plan=plan.as_dict(),
            thinking=mode.enable_thinking,
            parallel_tool_calls=mode.parallel_tool_calls,
            max_tokens=mode.max_tokens,
        )
        # Pasar al planner el ultimo assistant message para que detecte
        # turns de continuacion (e.g. agente pregunto perfil de streaming en
        # turn anterior; este turn el user responde "Ema" — sin esto, el
        # router decidiria subset=[] porque "Ema" no tiene keywords).
        last_assistant_text: str | None = None
        for msg in reversed(self.history):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                c = msg.get("content")
                if isinstance(c, str) and c.strip():
                    last_assistant_text = c
                    break
        # Hotfix F: pending_intent cross-turn rescue.
        # When a previous tool returned status='needs_user', the slot
        # holds the tool name so the next turn's planner can widen the
        # subset toward it — regardless of the user's reply text
        # (language-agnostic).
        pending_intent = (
            self.state.get_pending_intent(self._turn_counter)
            if hasattr(self.state, "get_pending_intent") else None
        )
        _mark_decide_phase(
            "pre_select_context",
            has_last_assistant=bool(last_assistant_text),
            has_pending_intent=bool(pending_intent),
        )
        selected_tool_names = select_tool_names(
            content, plan,
            safety_enabled=self.config.enable_safety,
            last_assistant_text=last_assistant_text,
            pending_intent=pending_intent,
        )
        _mark_decide_phase(
            "select_tool_names",
            tools=list(selected_tool_names or []),
        )
        # B2 (competidores): memory-guided tool-picking. Si turnos PASADOS con
        # intención similar tuvieron ÉXITO usando ciertas tools, las agregamos al
        # subset (cap 3) para que estén DISPONIBLES aunque el router no las elija
        # hoy. El LLM sigue decidiendo si llamarlas — sólo ensanchamos candidatos.
        # _recent_recalls ya viene del experience recall por embedding (arriba).
        # Gated GEMMA4_MEMORY_TOOLS (default off -> sin cambio).
        if _memory_tools_enabled():
            _mem_tools = _recalled_success_tools(
                getattr(self, "_recent_recalls", None), selected_tool_names)
            if _mem_tools:
                selected_tool_names = list(selected_tool_names) + _mem_tools
                self.trace.event(turn_id, "memory_tools_added", tools=_mem_tools)
        # Bug routing: lectura/análisis de archivo de datos/documento ->
        # tool específica (data_analysis/document), NO filesystem.read crudo. Las
        # tool_rules no bastaron (el 4B chico las ignora con filesystem disponible);
        # este override estructural por EXTENSIÓN saca filesystem del subset. Gated.
        if _file_tool_routing_enabled():
            _routed = _route_file_by_extension(content, list(selected_tool_names))
            if _routed != list(selected_tool_names):
                self.trace.event(turn_id, "file_routing_override", subset=_routed)
                selected_tool_names = _routed
        # Follow-up after an information turn: memory recall can widen the subset
        # with action tools from superficially similar past turns. If the previous
        # turn actually used information tools and the current turn is a short
        # question, keep this in the information domain so the LLM can continue
        # the same topic instead of searching local apps.
        _info_followup = _is_info_followup_question(
            raw_text_early or "", self._last_executed_tools)
        if _info_followup:
            before = list(selected_tool_names)
            meta = [t for t in before if t in _META_TOOLS]
            selected_tool_names = []
            for tool_name in ("web", "source_manager", "knowledge", *meta):
                if tool_name not in selected_tool_names:
                    selected_tool_names.append(tool_name)
            self.trace.event(
                turn_id, "info_followup_tools_from_context",
                previous_tools=list(self._last_executed_tools),
                before=before,
                after=selected_tool_names,
            )
            self._info_followup_note = (
                "# Information follow-up\n"
                "The current user message is a short follow-up to the previous "
                "information/research turn. Resolve omitted entities from the "
                "immediately preceding conversation and tool results. If the "
                "answer needs external, recent, or source-backed facts, call an "
                "available information tool instead of asking the user for the "
                "same context again. Answer in the user's selected language."
            )
            self._info_followup_prefetch_query = _contextual_info_query(
                raw_text_early or "", self.history)
            if mode.name in {"fast_action", "fast_info"}:
                mode = choose_mode(raw_text_early or "research", "research", self.config.max_tokens)
                self.trace.event(
                    turn_id, "info_followup_mode_research",
                    previous_tools=list(self._last_executed_tools),
                    mode=mode.name,
                )
        # If a phrase-trigger routine already fired this turn, drop
        # session.cancel_turn from the subset. The user's phrase was
        # claimed by their saved routine; the LLM should confirm what
        # ran, not propose a cancellation.
        if self._phrase_fires and "session" in selected_tool_names:
            selected_tool_names = [n for n in selected_tool_names if n != "session"]
            self.trace.event(turn_id, "session_suppressed_by_phrase_fire",
                             fires=len(self._phrase_fires))
        # CONTINUATION HEREDA TOOLS: si el subset no tiene NINGUNA tool de
        # dominio y el user esta dando una respuesta CORTA (continuation tras
        # un tool del turn previo: "Perfecto", "Si", "subelo un poco mas"),
        # heredar las tools del turno previo. Sin esto, "Prefiero cronologico"
        # tras un web research, o "subelo un poco mas" tras un audio.set_volume,
        # deja el subset solo con [session, safety] y el LLM, sin la tool real,
        # ALUCINA una llamada invalida (repro: "subelo un poco mas"
        # -> system({action:"audio.set_volume"}) -> invalid tool arguments).
        # NOTA: `if not selected_tool_names` (subset VACIO) no sirve acá,
        # porque el planner agrega session/safety, asi que nunca dispararia para
        # continuaciones reales. Dispara cuando no hay tool de dominio.
        _NON_DOMAIN_TOOLS = {"session", "safety", "state", "verify"}
        if not (set(selected_tool_names) - _NON_DOMAIN_TOOLS):
            raw_text = ""
            if isinstance(content, str):
                raw_text = content.strip()
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        raw_text = str(item.get("text") or "").strip()
                        break
            # Short continuation heuristic: <= 6 words AND no action verb.
            is_short_continuation = (
                raw_text and len(raw_text.split()) <= 6
            )
            # Step 5: fold the abstention decision INTO the
            # inheritance gate. Before, ANY short turn that the planner left
            # tool-less would inherit the prior tool — including deliberate
            # smalltalk/meta ("gracias", "qué hora es", "no uses tools"), which
            # is why with-context no-tool keep collapsed (0.58 -> 0.50). The
            # calibrated abstain head already separates "conversational, leave
            # it alone" from "deictic continuation with no own signal". If the
            # head is CONFIDENT this is no-tool, we do NOT inherit — the user
            # is talking, not continuing an action. Continuations like "ciérralo"
            # / "subelo" score LOW on abstain (action intent), so they still
            # inherit. This is the research's "context as a router input, not a
            # blind rescue".
            if is_short_continuation:
                try:
                    from ..safety_pkg.abstain_head import (
                        load_model as _ah_load, build_features as _ah_feats,
                        is_enabled as _ah_on,
                    )
                    if _ah_on():
                        _ahm = _ah_load()
                        if _ahm is not None:
                            from ..routing.intent_router import classify_intent as _ci
                            from ..routing import semantic_router as _sr_short
                            _isc = None
                            try:
                                _isc = _ci(raw_text)
                            except Exception:
                                _isc = None
                            _scored = []
                            try:
                                import os as _os_sem
                                _semantic_ready = bool(_sr_short.status().get("model_loaded"))
                                _semantic_cold = (
                                    _os_sem.environ.get("GEMMA4_SEMANTIC_COLD_LOAD", "0").strip().lower()
                                    in {"1", "true", "yes", "on"}
                                )
                                if _semantic_ready or _semantic_cold:
                                    _scored = _sr_short.suggest_tools_scored(raw_text, k=12)
                            except Exception:
                                _scored = []
                            _f = _ah_feats(raw_text, intent=_isc,
                                           scored=_scored,
                                           keyword_fired=False)
                            # A no-tool probability at/above the routing
                            # threshold means "really conversational" — skip
                            # inheritance. Using the gate's own threshold (not a
                            # higher floor) was the dev-tuned sweet spot: it
                            # preserves the isolated no-tool keep (0.612) under
                            # inheritance while real deictic continuations
                            # ("ciérralo"/"subelo", which score LOW on abstain)
                            # still inherit the prior tool.
                            # umbral POR IDIOMA (auditoría §7.5): el del turno si
                            # hay calibración propia, si no el global (threshold_for
                            # cae solo). _turn_lang viene del selector _reply_lang.
                            _lang = getattr(self, "_turn_lang", None)
                            _thr = (_ahm.threshold_for(_lang)
                                    if hasattr(_ahm, "threshold_for") else _ahm.threshold)
                            if _ahm.p_no_tool(_f) >= _thr:
                                # OVERRIDE por estado del SO: si el turno previo
                                # dejó una app/GUI abierta (tarea interactiva mid-
                                # flight), una continuación corta la está retomando
                                # — NO la trates como charla aunque el head lo crea.
                                # El abstain head solo ve el TEXTO; no ve que hay una
                                # calculadora abierta esperando la cuenta. "Pero
                                # quiero que lo hagas tú" tras abrir la calc dio
                                # p_no_tool=0.924 y colapsó el subset a [session],
                                # forzando al 4B a alucinar system(action=calculator).
                                _prev_gui = bool(
                                    set(self._last_executed_tools) & _GUI_CONTEXT_TOOLS
                                )
                                # EXCEPCIÓN al override: si el turno es
                                # una PREGUNTA-DEL-MUNDO clara (wants_knowledge: "cuál
                                # es el mejor lego batman", "qué tiempo hace") el user
                                # NO está operando la app abierta — quiere información.
                                # Heredar [app,gui,uia] le QUITA web/knowledge al 4B,
                                # que entonces emitía el search como TEXTO (`Web(...)`,
                                # caso real del log). wants_knowledge es intención por
                                # EMBEDDINGS multilingüe (no keywords; ley de producto)
                                # y MIDE info>action por margen. Los 'operate-app'
                                # ("ahora sumá 2+2", "hacelo tú") dan wants_knowledge
                                # =False (medido) → siguen heredando, sin regresión del
                                # caso calculadora. Fallback seguro: sin encoder/ error
                                # → False → se mantiene el override actual.
                                _wants_know = False
                                try:
                                    from ..routing.intent_router import wants_knowledge as _wk
                                    _wants_know = bool(_wk(raw_text))
                                except Exception:
                                    _wants_know = False
                                if _prev_gui and not _wants_know:
                                    self.trace.event(
                                        turn_id, "inherit_kept_gui_context",
                                        p_no_tool=round(_ahm.p_no_tool(_f), 3),
                                        prev_tools=list(self._last_executed_tools),
                                        user_text=raw_text[:60],
                                    )
                                elif _prev_gui and _wants_know:
                                    # Pregunta-del-mundo con app abierta: soltar el
                                    # contexto GUI para que el router ofrezca
                                    # web/knowledge. NO hereda.
                                    is_short_continuation = False
                                    self.trace.event(
                                        turn_id, "inherit_released_for_knowledge",
                                        p_no_tool=round(_ahm.p_no_tool(_f), 3),
                                        prev_tools=list(self._last_executed_tools),
                                        user_text=raw_text[:60],
                                    )
                                else:
                                    is_short_continuation = False
                                    self.trace.event(
                                        turn_id, "inherit_skipped_abstain",
                                        p_no_tool=round(_ahm.p_no_tool(_f), 3),
                                        user_text=raw_text[:60],
                                    )
                except Exception:
                    pass
            if is_short_continuation:
                # F-005: gap temporal > INHERIT_TTL_SEC => no heredar
                # (user volvio tras mucho tiempo, contexto del turn previo
                # ya no es relevante y heredar tools peligrosos es riesgoso).
                now = time.time()
                ttl_expired = (
                    self._last_turn_ts is not None
                    and (now - self._last_turn_ts) > INHERIT_TTL_SEC
                )
                if ttl_expired:
                    self.trace.event(
                        turn_id, "inherit_tools_ttl_expired",
                        gap_sec=int(now - (self._last_turn_ts or now)),
                        user_text=raw_text[:60],
                    )
                else:
                    # PRIMARY source: the previous turn's actually-executed
                    # tools, tracked in _last_executed_tools. This SURVIVES
                    # history compaction (which strips tool_calls/tool
                    # messages), so the history scan below usually finds
                    # nothing. Without this, continuations never inherited.
                    prev_tools: list[str] = list(self._last_executed_tools)
                    # Fallback: scan history (works when compaction hasn't run
                    # yet, e.g. mid-turn continuations).
                    for msg in reversed(self.history):
                        if prev_tools:
                            break
                        if not isinstance(msg, dict):
                            continue
                        if msg.get("role") == "tool":
                            # Tool result messages carry name field.
                            name = msg.get("name")
                            if isinstance(name, str) and name:
                                if name not in prev_tools:
                                    prev_tools.append(name)
                        elif msg.get("role") == "assistant":
                            tcs = msg.get("tool_calls") or []
                            for tc in tcs:
                                fn = (tc or {}).get("function") or {}
                                name = fn.get("name")
                                if isinstance(name, str) and name and name not in prev_tools:
                                    prev_tools.append(name)
                            if prev_tools:
                                # Stop at the most recent assistant turn that
                                # used tools — we have what we need.
                                break
                    # F-005: filtrar tools peligrosos de la herencia.
                    if prev_tools:
                        filtered = [
                            t for t in prev_tools
                            if t not in DANGEROUS_TOOLS_NEVER_INHERIT
                        ]
                        dropped = [t for t in prev_tools if t in DANGEROUS_TOOLS_NEVER_INHERIT]
                        if dropped:
                            self.trace.event(
                                turn_id, "inherit_tools_filtered_dangerous",
                                dropped=dropped, kept=filtered,
                            )
                        prev_tools = filtered
                    # Si el contexto previo era GUI (app/window abierta), la
                    # continuación suele necesitar OPERAR esa app por teclado,
                    # no sólo re-abrirla. P.ej. tras "abre la calculadora" sólo
                    # se ejecutó `app`; "ahora sumá 2+2" requiere `gui` (type +
                    # keypress) que no estaba en prev_tools. Sumamos las tools de
                    # síntesis (gui, uia) al subset heredado para que el patrón
                    # universal "operar la app abierta por teclado" sea posible.
                    if prev_tools and (set(prev_tools) & _GUI_CONTEXT_TOOLS):
                        for _t in ("gui", "uia"):
                            if _t not in prev_tools:
                                prev_tools.append(_t)
                    if prev_tools:
                        selected_tool_names = prev_tools[:6]
                        self.trace.event(
                            turn_id, "tools_inherited_from_continuation",
                            tools=selected_tool_names,
                            user_text=raw_text[:60],
                        )
        semantic_fallback = bool(getattr(select_tool_names, "_last_fallback_used", False))
        _mark_decide_phase(
            "post_select_adjustments",
            tools=list(selected_tool_names or []),
            semantic_fallback=semantic_fallback,
        )
        # router_v2 (BM25+RRF hybrid) was removed. All four router
        # research reports agreed it was structurally wrong for short voice
        # queries (TF collapses to 1; RRF amplifies the degenerate lexical
        # ranker's noise) and a live probe caught it routing garbage. The
        # unified router — fine-tuned encoder + Tool2Vec + calibrated abstain
        # head, all driven through select_tool_names — replaced it with a
        # measured-better result (holdout recall 0.835->0.881, no-tool
        # 0.512->0.628). See docs/architecture/router_rebuild_2026_05_21.md.
        # Persona nudge: ensure the persona's preferred tools are in the
        # subset. Append without duplicating; _cap_tools later trims if it
        # blows the limit. Default persona has no preferred tools so this is
        # a no-op for most users.
        if self._persona.preferred_tools:
            existing = set(selected_tool_names)
            for tool_name in self._persona.preferred_tools:
                if tool_name not in existing:
                    selected_tool_names.append(tool_name)
                    existing.add(tool_name)
        # Accessibility-mode nudge: igual patrón que la persona. En 'movilidad'
        # el agente DEBE tener a mano las tools de control del PC (computer_use/
        # uia/gui) para poder actuar sin pedirle al usuario que toque nada; en
        # 'no_vidente', las de lectura/control de pantalla. 'normal' no tiene
        # preferred_tools -> no-op. Fallback seguro ante cualquier error.
        try:
            from .. import accessibility as _a11y_sub
            _a11y_prefs = _a11y_sub.get_active_mode().preferred_tools
        except Exception:
            _a11y_prefs = ()
        # GUARD (bug medido): NO inyectar las tools del modo si el router
        # ABSTUVO (no eligió ninguna tool de dominio) — eso significa charla/pregunta
        # de identidad/smalltalk ("¿quién eres?", "gracias"). Inyectar gui/computer_use/
        # uia ahí hacía que el 4B, en modo movilidad, sacara un screenshot y buscara
        # texto en la pantalla para responder "¿quién eres?" (absurdo). Las
        # preferred_tools deben REFORZAR un turno que YA es de acción (el router
        # ofreció ≥1 tool de dominio), no FABRICAR uno desde una pregunta de charla.
        try:
            _has_domain_pick = bool(_domain_subset(list(selected_tool_names)))
        except Exception:
            _has_domain_pick = bool(selected_tool_names)
        if _a11y_prefs and _has_domain_pick:
            existing = set(selected_tool_names)
            for tool_name in _a11y_prefs:
                if tool_name not in existing:
                    selected_tool_names.append(tool_name)
                    existing.add(tool_name)
        # The NLI-based capability classifier (Bug 1) was removed:
        # 3.2% cache hit rate over 5 days of use (vs 20% kill threshold per
        # 08_findings.md §2.10) for a 280MB mDeBERTa model + worker thread.
        # The keyword planner + semantic_router fallback remain.
        #
        # PREFIJO ESTABLE (latencia): anteponer el core-set fijo a los picks del
        # router para que el prefijo del prompt (reglas+schemas del core) sea
        # idéntico turno-a-turno y el prefix-cache de llama.cpp lo reuse (~100ms
        # vs ~1100ms reprocesando). Los picks extra del router quedan al final.
        # Gate GEMMA4_STABLE_TOOL_PREFIX=0 revierte. Ver _CACHE_CORE_SET.
        _router_picks = list(selected_tool_names)
        # MULTI-INTENT carry (Fase 2 computer-use): si venimos de una cláusula
        # previa que abrió/enfocó algo (app/gui/window...), forzar esas tools en
        # el subset para que "escribí X" tras "abrí Notepad" pueda actuar sobre
        # ese contexto en vez de caer a charla. Solo activo dentro de
        # _run_multi_intent (self._splitting True + carry no vacío). Bypassa el
        # veto conversacional porque en un comando compuesto sabemos que NO es
        # smalltalk. Universal (no depende del idioma del verbo).
        _carry = getattr(self, "_mi_carry_tools", None)
        if _carry and getattr(self, "_splitting", False):
            for _t in _carry:
                if _t not in selected_tool_names:
                    selected_tool_names.append(_t)
            self.trace.event(turn_id, "multi_intent_carry",
                             carried=_carry, subset=selected_tool_names)
        # NOTA: acá vivía un bloque que, si una ventana abierta matcheaba
        # el comando, inyectaba uia/gui y DROPPEABA distractores incluido `whatsapp`.
        # Eso REGRESIONÓ los comandos de WhatsApp ("escribile a X en wsp"): si Discord
        # u otra ventana coincidía con un token del comando, se sacaba `whatsapp` y el
        # comando perdía su tool. SE ELIMINÓ: la operación-en-app ya la maneja la capa
        # universal _try_computer_use (short-circuit ANTES del LLM, línea ~846). Si esa
        # capa no aplica (no hay app abierta mencionada / server caído), el router/LLM
        # decide normalmente — sin cirugía de subset que rompa WhatsApp/Discord.
        selected_tool_names = _stabilize_tool_order(selected_tool_names)
        if selected_tool_names != _router_picks:
            self.trace.event(turn_id, "tool_prefix_stabilized",
                             router_picks=_router_picks,
                             stabilized=selected_tool_names)
        # Flag por turno: la pregunta fast_info es de ESTADO LOCAL (pantalla/
        # sistema). Lo consume el gate del forced-retry: prosa sin tool en estas
        # preguntas = fabricacion, no respuesta parametrica valida.
        self._fast_info_local_state = False
        if mode.name == "fast_info" and _fast_info_no_tools_enabled() and selected_tool_names:
            # Solo se suprimen los schemas ESPECULATIVOS (web/knowledge/...):
            # eran los que causaban loops y outliers en info parametrica
            # ('hablame de Mortal Kombat'). Las tools de ESTADO LOCAL que el
            # router eligio se MANTIENEN: "que hay en la pantalla" / "que hora
            # es" no son parametricas — el core ordena gui+vision/system(time)
            # y con subset vacio el modelo queda ciego y responde inventando
            # (MEDIDO 2026-06-11: subset vacio + core pidiendo screenshot →
            # reply roto; misma mecanica que la hora fabricada).
            _local_state_keep = {"gui", "uia", "vision", "system", "window",
                                 "audio", "device_settings"}
            _kept = [t for t in selected_tool_names if t in _local_state_keep]
            _suppressed = [t for t in selected_tool_names if t not in _local_state_keep]
            # El mission plan tambien sugiere tools por paso. Si sugirio una de
            # estado local que el subset NO trajo (p.ej. encoder frio → fallback
            # generico sin gui), la sumamos al final (el orden del router manda):
            # sin esto, "que hay en la pantalla" queda sin el schema que el core
            # ordena usar y el modelo responde inventando.
            _plan_local: set[str] = set()
            try:
                for _step in (plan.steps or []):
                    for _t in (getattr(_step, "suggested_tools", None) or []):
                        if _t in _local_state_keep:
                            _plan_local.add(_t)
                            if _t not in _kept:
                                _kept.append(_t)
            except Exception:
                pass
            _kept = _kept[:5]
            # El discriminador es el PLAN (MEDIDO 2026-06-12): "que hay en la
            # pantalla"/"que hora es"/"cuanta RAM tengo" → el planner sugiere
            # uia/gui/system (estado local: prosa sin tool = FABRICADA); "que es
            # la RAM"/"cual es la capital de Francia" → sugiere web/knowledge
            # (parametrica valida — forzar tool ahi quemaba ~10.8s medidos).
            # needs_pc_action NO sirve (True en ambos casos); y el subset puede
            # traer tools locales inyectadas post-select que no implican nada.
            self._fast_info_local_state = bool(_kept) and bool(_plan_local)
            if _suppressed:
                selected_tool_names = _kept
                self.trace.event(
                    turn_id,
                    "fast_info_tools_suppressed",
                    dropped=_suppressed,
                    kept=_kept,
                    reason="parametric_info_low_latency",
                )
        if mode.name == "research":
            _research_orig = list(selected_tool_names)
            _research_keep = {"web", "knowledge", "source_manager", "session"}
            selected_tool_names = [
                t for t in selected_tool_names if t in _research_keep
            ]
            if "web" not in selected_tool_names:
                selected_tool_names.insert(0, "web")
            if selected_tool_names != _research_orig:
                self.trace.event(
                    turn_id,
                    "research_subset_slimmed",
                    dropped=[t for t in _research_orig if t not in selected_tool_names],
                    kept=list(selected_tool_names),
                )
        # HARD CAP FINAL despues de persona+a11y+carry+stabilize.
        # MEDIDO: a11y mode `no_vidente` agrega 5 tools (vision/uia/gui/
        # computer_use/browser_real) DESPUES del cap del planner; suma puede
        # llegar a 11 tools -> prompt ~14.6k toks -> dispara CUDA #22527.
        # Hard cap mantiene los primeros N (orden ya estabilizado por priority).
        # Override via GEMMA4_HARD_TOOL_CAP=N.
        import os as _os_cap
        try:
            _hard_cap = int(_os_cap.environ.get("GEMMA4_HARD_TOOL_CAP", "5"))
        except ValueError:
            _hard_cap = 5
        if _hard_cap > 0 and len(selected_tool_names) > _hard_cap:
            _capped_orig = list(selected_tool_names)
            # Preservar `session` (siempre al final por contrato) si estaba.
            _had_session = "session" in selected_tool_names
            _without_session = [t for t in selected_tool_names if t != "session"]
            _without_session = _without_session[: _hard_cap - (1 if _had_session else 0)]
            selected_tool_names = _without_session + (["session"] if _had_session else [])
            self.trace.event(turn_id, "hard_cap_applied",
                             original=_capped_orig,
                             kept=selected_tool_names,
                             cap=_hard_cap,
                             reason="prevent CUDA #22527 crash on prompt >~13k toks")
        selected_schemas = self.tools.schemas_for_names(selected_tool_names)
        self.trace.event(turn_id, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas), semantic_fallback=semantic_fallback, persona=self._persona.name)
        _progress(progress, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas))
        _mark_decide_phase(
            "schemas_and_caps",
            tools=list(selected_tool_names or []),
            schema_count=len(selected_schemas),
        )

        # Reasoning-for-tools upgrade (9da4fd3). If a DOMAIN tool is in the subset
        # and the picked mode has thinking OFF, upgrade to quick_action
        # (thinking ON) — Gemma 4 emits tool-calls reliably only with reasoning
        # (E4B plain-OFF: 2-4/6 through the full agent).
        #
        # MEASURED: tool_choice=required + thinking-OFF was tested as a way
        # to recover the golden-era ~1s pass-1 with reliability. It works
        # for clear commands (abre steam, mutea: 0.5-1.8s) BUT on ambiguous ones
        # ("quita el silencio") the forced grammar runs away to max_tokens with
        # NO tool-call (200 tok, ~6s, then forced-retry) — worse than thinking,
        # and exactly the >5s outliers we're trying to kill. REJECTED: thinking
        # ON is the reliable floor. Latency is recovered via the orthogonal
        # safe wins (swa-full prefix-reuse, CUDA prefill, cap-10 subset, pass-2
        # slimming, streaming TTS) that don't trade reliability. See
        # latency_golden_eras.md + latency_research_prompt.md.
        if not mode.enable_thinking:
            try:
                _dom = _domain_subset(list(selected_tool_names))
                # LATENCIA: NO upgradear a thinking cuando el turno es
                # INFORMATIVO (fast_info) y los únicos domain-tools ofrecidos son
                # de info-retrieval (web/knowledge/memory/...). MEDIDO en vivo:
                # esas preguntas el modelo las responde de su conocimiento SIN
                # llamar la tool, así que el thinking-para-tool-calling es puro
                # costo (fs2 "GTA5" 15.6s, cx5 "RAM" 13.5s con thinking ON; las
                # mismas OFF dan 0.4-2s y MEJOR calidad — el reasoning dejaba el
                # content vacío). El upgrade SÍ aplica a tools de ACCIÓN (donde
                # Gemma necesita reasoning para emitir el tool-call fiable).
                # fast_info = una PREGUNTA informativa. El modelo la responde de
                # su conocimiento; NO la upgradeamos a thinking aunque el router
                # haya ofrecido tools especulativamente (web/system/etc.) — esas
                # preguntas casi nunca llaman la tool, y el thinking-para-tool es
                # puro costo (medido: cx5 "RAM" 14.7s con upgrade vs ~2s sin). Si
                # excepcionalmente necesita una tool, el forced-tool-retry la
                # rescata. Para fast_action (smalltalk/comando) el upgrade SÍ
                # aplica salvo que los tools sean sólo info-retrieval.
                _only_info = bool(_dom) and all(
                    t in _INFO_RETRIEVAL_TOOLS for t in _dom)
                _skip_upgrade = (mode.name in {"fast_info", "research"}) or (
                    _only_info and mode.name == "fast_action")
                if _dom and not _skip_upgrade:
                    # choose_mode ya top-level (línea 18).
                    mode = choose_mode("quick_action", "quick_action", self.config.max_tokens)
                    self.trace.event(turn_id, "mode_upgraded_for_tools",
                                     to="quick_action", tools=list(selected_tool_names))
            except Exception:
                pass
        # Persist subset for the fallback streak helper (used to surface
        # plausible hints when the user repeats the same failed phrase).
        self._last_router_subset = list(selected_tool_names)
        # Telemetry: separate keyword-vs-semantic breakdown so we can
        # diagnose WHY a turn ended at the fallback. Local only — never sent.
        try:
            from ..routing.planner import _suggest_tools as _kw_suggest
            kw_hits = _kw_suggest(raw_text_early or "")
        except Exception as _exc:
            try:
                self.trace.event(
                    turn_id, "silent_fallback",
                    component="planner_keyword_hits",
                    error=f"{type(_exc).__name__}: {_exc}",
                )
            except Exception:
                pass
            kw_hits = []
        sem_hits: list[str] = []
        if semantic_fallback:
            try:
                from ..routing.semantic_router import suggest_tools_semantic
                sem_hits = suggest_tools_semantic(raw_text_early or "", k=6)
            except Exception as _exc:
                try:
                    self.trace.event(
                        turn_id, "silent_fallback",
                        component="semantic_router",
                        error=f"{type(_exc).__name__}: {_exc}",
                    )
                except Exception:
                    pass
                sem_hits = []
        self.trace.event(
            turn_id, "router_reasoning",
            user_text=(raw_text_early or "")[:200],
            kw_matches=list(kw_hits),
            semantic_matches=list(sem_hits),
            final_subset=list(selected_tool_names),
            phrase_fires=len(self._phrase_fires or []),
        )
        self._compact_completed_history()
        # EAGER read-only (opt-in GEMMA4_EAGER_READONLY, default OFF). Si el
        # router ofreció una tool de SOLO-LECTURA (system.time/cpu_ram_gpu/disk/
        # battery), dispararla AHORA en background: corre en paralelo al pase-1
        # del LLM que sigue en _execute_turn, así si el LLM la pide el resultado
        # ya está listo (ahorra el tiempo de la tool). Si el LLM no la pide o
        # falla, se descarta — es read-only puro, sin efecto. SEGURO por diseño:
        # eager_candidates exige 3 barreras (tabla declarativa + verbo-de-lectura
        # estructural + clasificador de seguridad); NUNCA dispara una escritura.
        # Fail-safe: ante cualquier error, el cache queda None y el dispatch corre
        # la tool normal.
        # Rama Experimentando: SIN eager_readonly (no se pre-ejecutan tools
        # read-only antes del LLM). El LLM pide las tools que necesita.
        self._eager_cache = None
        _mark_decide_phase("decide_done")
        return TurnDecision(
            turn_id=turn_id,
            mode=mode,
            plan=plan,
            raw_text_early=raw_text_early,
            pending_intent=pending_intent,
            selected_tool_names=selected_tool_names,
            semantic_fallback=semantic_fallback,
            selected_schemas=selected_schemas,
        )

    def _fg_complete_arg(self, user_text: str, tool: str, action: str, field: str) -> str | None:
        """El LLM de habla (QAT) extrae el valor que FunctionGemma dejó vacío, del texto del
        usuario. Devuelve el valor, o None si el usuario NO lo especificó (entonces NO se completa
        y el tool pide aclaración — honestidad: jamás se inventa). No usa regex ni listas por idioma:
        el LLM lo decide con el contexto del turno. Llamada corta y greedy (latencia acotada)."""
        prompt = (
            f"El usuario dijo: \"{(user_text or '').strip()}\"\n"
            f"Se va a ejecutar la acción '{action}' pero falta el dato '{field}'. "
            f"¿Cuál es el '{field}' EXACTO según lo que dijo el usuario? Respondé SOLO ese valor "
            f"(en el idioma del usuario), sin comillas ni explicación. Si el usuario NO lo "
            f"especificó, respondé exactamente: NINGUNO"
        )
        try:
            resp = self.client.chat(
                [{"role": "user", "content": prompt}],
                tools=None, enable_thinking=False, parallel_tool_calls=False,
                max_tokens=24, greedy=True,
                sampling={"temperature": 0.0, "top_p": 1.0, "top_k": 1},
                timeout_s=20.0,
            )
            choice = (resp.get("choices") or [{}])[0]
            val = ((choice.get("message") or {}).get("content") or "").strip().strip("\"'").strip()
            if not val or len(val) > 60:
                return None  # vacío o rambling -> no es un valor limpio
            # sentinel "no especificado" (multilingüe defensivo): el LLM responde en el idioma del
            # user, pero le pedimos la palabra fija NINGUNO; aceptamos variantes obvias.
            if val.split()[0].upper().strip(".,:;!?") in {"NINGUNO", "NONE", "NADA", "N/A", "NA"}:
                return None
            return val
        except Exception:
            return None

    def _chat_streaming(
        self,
        msgs: list[dict[str, Any]],
        *,
        model: str | None,
        max_tokens: int,
        thinking_budget: int | None,
        timeout_s: float | None,
        turn_id: str,
        tools: list[dict[str, Any]] | None = None,
        enable_thinking: bool = False,
        greedy: bool = False,
        sampling: dict[str, Any] | None = None,
        guard_check: bool = False,
    ) -> dict[str, Any]:
        """Stream a reply pass via ``chat_stream``, feeding sanitized prose to the
        per-turn TTS sink as it arrives, and return a ``chat()``-shaped dict so the
        rest of ``_execute_turn`` is unchanged.

        Truthfulness is ENFORCED, not assumed:
        - SUMMARY pass (``guard_check=False``, a tool ran): the content-REPLACING
          guards are pass-through, so streamed prose == final prose.
        - INFO pass (``guard_check=True``, no tool): the replacing guards CAN fire,
          so before voicing each increment we run the REAL detectors
          (``detect_action_claim_without_evidence`` / ``reply_claims_action``) on
          the accumulated buffer; the instant one would fire we ABORT (stop
          feeding) and mark not-streamed, so the runner voices the FULL guarded
          reply instead. Everything already voiced passed the detectors (clean).
        Prose is sanitized incrementally; if sanitize shrinks already-voiced text
        we also abort. Full RAW content is returned so finalize re-applies the
        exact same sanitize + guards as the blocking path.
        """
        from ..support.reasoning import sanitize_text as _san
        sink = getattr(self, "_active_tts_sink", None)
        _guard_check = bool(guard_check)

        def _guard_fires(text: str) -> bool:
            # Rama Experimentando: sin honesty-guard sobre el stream. Nunca
            # aborta el streaming por "claim sin evidencia".
            return False

        acc_raw = ""
        fed = ""  # sanitized prose already handed to the sink (what was voiced)
        aborted = False
        final_content = ""
        final_tool_calls: list[dict[str, Any]] = []
        final_finish: str | None = None
        for ev in self.client.chat_stream(
            msgs, tools=tools, enable_thinking=enable_thinking,
            thinking_budget=thinking_budget, max_tokens=max_tokens,
            timeout_s=timeout_s, model=model, greedy=greedy, sampling=sampling,
        ):
            etype = ev.get("type")
            if etype == "delta":
                piece = ev.get("content_delta") or ""
                if not piece or aborted or sink is None:
                    continue
                acc_raw += piece
                san = _san(acc_raw)
                if not san.startswith(fed):
                    # sanitize changed/removed already-voiced text -> stop feeding.
                    aborted = True
                    self.trace.event(turn_id, "tts_stream_sanitize_abort",
                                     fed=fed[:80], san=san[:80])
                    continue
                if _guard_fires(san):
                    # the new text would trip a content-replacing guard -> NEVER
                    # voice it; the runner will speak the full guarded reply.
                    aborted = True
                    self.trace.event(turn_id, "tts_stream_guard_abort", san=san[:120])
                    continue
                new = san[len(fed):]
                # MARKUP GUARD (2026-06-10): los patrones de sanitize_text son de
                # bloque COMPLETO (exigen el tag de cierre o un \n) — en el stream
                # incremental el markup llega DE A PEDAZOS y se vocaba antes de
                # que el patrón cerrara (MEDIDO en vivo: '<|tool_call>call:window
                # {action:maximize' vocado crudo al sink). Estructural: un '<|'
                # confirmado en lo NUEVO = el modelo emite sintaxis de tool-call
                # como texto -> abortar el feed (el runner voca el reply final,
                # que sí pasa por sanitize completo). Un sufijo que PUEDE ser una
                # apertura ('<', '<|too', '<unus') se RETIENE hasta que el próximo
                # delta lo desambigüe (prosa legítima '2 < 3' se libera intacta).
                if "<|" in new:
                    aborted = True
                    self.trace.event(turn_id, "tts_stream_markup_abort",
                                     san=san[-120:])
                    continue
                _m_tail = _TTS_MARKUP_OPENER_TAIL_RE.search(new)
                if _m_tail:
                    new = new[:_m_tail.start()]
                if new:
                    try:
                        sink(new)
                    except Exception:  # noqa: BLE001
                        aborted = True
                        continue
                    fed = fed + new
            elif etype == "final":
                final_content = ev.get("content") or acc_raw
                final_tool_calls = ev.get("tool_calls") or []
                final_finish = ev.get("finish_reason")
        # If the model called a tool (narrate-then-call on an info pass), the
        # streamed prose was a pre-tool DRAFT, not the final answer -> don't claim
        # it as streamed (the runner voices the post-tool summary). The draft was
        # honest, guard-checked prose; voicing it + the summary is redundant but
        # never a lie. Keeps "voiced == final" true for the pure-prose info win.
        self._tts_streamed = bool(fed) and not aborted and not final_tool_calls
        self._tts_streamed_text = fed if self._tts_streamed else ""
        if guard_check:
            # Mark that we streamed an INFO (no-tool) pass. If the turn later runs
            # a tool anyway (the model emits a web-call as text that the RESCUE
            # parser executes -> a post-prose tool+summary), finalize demotes this
            # to NOT-streamed so the runner voices the verified post-tool final
            # (never bypass verification; the streamed knowledge prose was honest).
            self._tts_info_stream = self._tts_streamed
        self.trace.event(turn_id, "tts_streamed", chars=len(fed), aborted=aborted,
                         guard_check=guard_check, tool_called=bool(final_tool_calls))
        return {
            "choices": [{
                "message": {"content": final_content, "tool_calls": final_tool_calls},
                "finish_reason": final_finish or "stop",
            }],
        }

    def _feed_tts_tail(self, final_spoken: str, turn_id: str) -> None:
        """After finalize built the guarded+footer reply, voice ONLY the tail not
        already streamed (an appended hedge/footer). startswith-guarded: if the
        final text diverges from what was voiced (unreachable when a tool ran,
        since the replacing guards are pass-through) we log and voice nothing
        extra -- never double-speak, never contradict."""
        sink = getattr(self, "_active_tts_sink", None)
        spoken = getattr(self, "_tts_streamed_text", "") or ""
        if sink is None or not getattr(self, "_tts_streamed", False):
            return
        if final_spoken.startswith(spoken):
            tail = final_spoken[len(spoken):]
            if tail.strip():
                try:
                    sink(tail)
                except Exception:  # noqa: BLE001
                    pass
        elif spoken.startswith(final_spoken):
            return  # final is a prefix of what we voiced (guard trimmed) -> nothing to add
        else:
            self.trace.event(turn_id, "tts_stream_tail_divergence",
                             spoken=spoken[:80], final=final_spoken[:80])

    def _execute_turn(self, content: str | list[dict[str, Any]], decision: TurnDecision, progress: ProgressCallback | None = None) -> AgentReply:
        """Execute phase of a turn.

        Runs the LLM loop iteratively: chat() -> tool dispatch ->
        feedback -> chat() ... up to max_agent_turns. Inside the loop
        the assistant's reply is post-processed (verifiers, accessibility
        nudges, mission outcome, footer); termination is by
        max_turns/loop_aborted/LLM-said-stop. Returns the AgentReply
        terminal of the turn.
        """
        turn_id = decision.turn_id
        mode = decision.mode
        plan = decision.plan
        raw_text_early = decision.raw_text_early
        pending_intent = decision.pending_intent
        selected_tool_names = decision.selected_tool_names
        semantic_fallback = decision.semantic_fallback
        selected_schemas = decision.selected_schemas
        self.history.append({"role": "user", "content": _compact_live_content(content)})
        events: list[ToolEvent] = []
        failure_log: list[dict[str, Any]] = []
        replan_done = False
        research_fallback_answer_only = False
        self._research_fallback_answer_pending = False
        self._research_fallback_answer_reprompted = False

        # Loop detector: registra cada tool execution con result canonicalizado y
        # detecta 6 patrones de stuck (repeat, unknown_tool, ping_pong, circuit
        # breaker, vision_not_found, no_progress). Two-tier escalation: warning -> critical.
        # Vive por-turn (un user request); se evita carry-over que confunda al
        # LLM entre preguntas distintas.
        from ..safety_pkg.loop_detection import LoopState, GLOBAL_CIRCUIT_BREAKER as _LOOP_CIRCUIT_BREAKER
        loop_state = LoopState()
        loop_aborted = False  # se setea True si detectamos critical

        # Structural per-tool verifier (TIER 1 #2). Cada tool ejecutada produce
        # un VerifierOutcome (confirmed True/False/None) que se acumula y al
        # final del turn se rinde como footer honesto en el reply. Si el
        # outcome trae evidence_keys, los inyecta al loop_state para resetear
        # warning_count en progreso real (integration con TIER 1 #1).
        from .. import verifiers as _verifiers_registry  # noqa: F401  registra via decorators
        from ..safety_pkg.verify_core import (
            VerifierOutcome,
            classify_failure as _classify_failure,
            retry_budget_for as _retry_budget_for,
            ERR_MISSING_PRECONDITION, ERR_PARAM_MISMATCH, ERR_TRANSIENT,
            ERR_TOOL_NOT_FOUND, ERR_UNKNOWN,
        )
        verifier_outcomes: list[VerifierOutcome] = []
        # Contador de retries GASTADOS por clase de error
        # en ESTE turno. Cuando una clase agota su budget (retry_budget_for), el
        # hint deja de pedir reintento y pasa a "escalá honestamente". Ataca el
        # "466/513 retries desperdiciados". Vive en el frame del turno -> se
        # resetea solo en cada _execute_turn (no leakea entre turnos).
        _retry_spent: dict[str, int] = {}

        # TIER 2 #5: MissionGoal — verifier estructural por-mision (Voyager pattern).
        # Construido al inicio del turn desde el user_text crudo. Cada tool call
        # marca su contribucion al objetivo via mission_goal.update_with_tool.
        # Al final, compute_mission_outcome combina con los per-tool verifier
        # outcomes para producir un MissionOutcome con status semantico
        # (COMPLETED/PARTIAL/FAILED/TOOL_OK_VERIFIER_INCONCLUSIVE/...).
        from ..mission.mission_goal import MissionGoal as _MissionGoal
        from ..mission.mission_outcome import (
            compute_mission_outcome as _compute_mission_outcome,
            build_tool_records as _build_tool_records,
        )
        # from_user_text runs regex intent-detection on the user text. A bug
        # there must not crash the turn before any LLM call — fall back to an
        # empty MissionGoal (no expected outcomes -> footer simply stays quiet).
        try:
            mission_goal = _MissionGoal.from_user_text(raw_text_early or "")
        except Exception as _mg_exc:  # noqa: BLE001
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "MissionGoal.from_user_text failed: %s", _mg_exc)
            # Direct constructor — can't re-run the regex path that just failed.
            mission_goal = _MissionGoal(user_text="", expected=[])
        validator_retries_used = 0

        _prefetch_query = (getattr(self, "_info_followup_prefetch_query", "") or "").strip()
        if (
            _prefetch_query
            and _research_tool_fallback_enabled()
            and "web" in selected_tool_names
        ):
            _call_id = f"info_followup_prefetch_{turn_id}"
            _prefetch_args = {"action": "search", "query": _prefetch_query}
            _prefetch_call = {
                "id": _call_id,
                "type": "function",
                "function": {
                    "name": "web",
                    "arguments": json.dumps(_prefetch_args, ensure_ascii=False),
                },
            }
            self.history.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [_prefetch_call],
            })
            self.trace.event(
                turn_id, "info_followup_prefetch",
                tool="web", action="search", query=_prefetch_query[:220],
            )
            self.trace.event(
                turn_id, "tool_call",
                name="web", args=_prefetch_args, in_subset=True, parse_error=None,
            )
            _progress(progress, "tool_start", name="web", index=1)
            try:
                _prefetch_result = self.tools.execute("web", _prefetch_args)
            except Exception as _prefetch_exc:  # noqa: BLE001
                _prefetch_result = {
                    "ok": False,
                    "status": "failed",
                    "verified": False,
                    "error": f"{type(_prefetch_exc).__name__}: {_prefetch_exc}",
                    "completion_status": "failed",
                }
            if not isinstance(_prefetch_result, dict):
                _prefetch_result = {
                    "ok": False,
                    "status": "failed",
                    "verified": False,
                    "error": "web prefetch returned non-dict result",
                    "completion_status": "failed",
                }
            _prefetch_event = ToolEvent(
                name="web", args=_prefetch_args, result=_prefetch_result)
            events.append(_prefetch_event)
            self.trace.event(turn_id, "tool_result", name="web", result=_prefetch_result)
            # Rama Experimentando: sin verifier; solo tracking de misión por ok crudo.
            mission_goal.update_with_tool(
                "web", _prefetch_args, bool(_prefetch_result.get("ok")))
            _progress(
                progress,
                "tool_end",
                name="web",
                ok=bool(_prefetch_result.get("ok")),
                status=str(_prefetch_result.get("status") or ""),
                verified=_prefetch_result.get("verified"),
                index=len(events),
            )
            self.history.append({
                "role": "tool",
                "tool_call_id": _call_id,
                "content": json.dumps(
                    _compact_tool_result("web", _prefetch_args, _prefetch_result),
                    ensure_ascii=False,
                ),
            })
            self.history.append({
                "role": "user",
                "content": (
                    "[system note] You already have the search results for this "
                    "information follow-up. Answer now from the returned tool "
                    "evidence in the user's selected language. Do not acknowledge "
                    "the search; give the factual answer. Do not call more tools."
                ),
            })
            selected_tool_names = []
            selected_schemas = []
            mode = choose_mode(raw_text_early or "", "fast_info", self.config.max_tokens)
            self._research_fallback_answer_pending = True

        # prompt_built_tokens — emit ONCE per turn (before the
        # retry loop) so we can track p50/p95 of input size. Estimation is
        # chars/4, conservative for a multilingual prompt. We materialize
        # the messages list here to measure exactly what the first chat
        # call will see; subsequent retry iterations may shrink the subset
        # but the FIRST attempt dominates the latency budget.
        try:
            _prompt_build_t0 = time.perf_counter()
            _initial_messages = self._messages(
                mode, plan,
                selected_tool_names=selected_tool_names,
                user_text=raw_text_early,
                route_context=True,  # mide lo que realmente verá la 1ª llamada
            )
            _system_chars = sum(
                len(str(m.get("content") or "")) for m in _initial_messages
                if m.get("role") == "system"
            )
            _schemas_chars = sum(len(json.dumps(s)) for s in selected_schemas)
            _history_chars = sum(
                len(str(m.get("content") or "")) for m in _initial_messages
                if m.get("role") != "system"
            )
            _total_chars = _system_chars + _schemas_chars + _history_chars
            self.trace.event(
                turn_id, "prompt_built",
                system_chars=_system_chars,
                schemas_chars=_schemas_chars,
                history_chars=_history_chars,
                total_chars=_total_chars,
                estimated_tokens=_total_chars // 4,
                schemas_count=len(selected_schemas),
                wall_ms=round((time.perf_counter() - _prompt_build_t0) * 1000.0, 3),
                since_turn_start_ms=round(
                    (time.perf_counter() - getattr(self, "_turn_perf_t0", time.perf_counter())) * 1000.0,
                    3,
                ),
            )
        except Exception:
            # Telemetry must never break the agent.
            pass

        for _turn in range(self.config.max_agent_turns):
            _progress(
                progress,
                "llm_start",
                turn=_turn + 1,
                max_turns=self.config.max_agent_turns,
                tools=len(events),
            )
            # Reasoning only helps the model DECIDE/emit the tool-call. Once a
            # tool has run this turn, the next LLM iteration just summarizes the
            # result ("Listo, abrí Steam") — that needs no thinking, and leaving
            # it on roughly DOUBLES the turn latency (a second reasoning pass on
            # a 4B CPU model). So enable thinking only while no tool has run yet.
            _think_now = mode.enable_thinking and len(events) == 0
            _messages_build_t0 = time.perf_counter()
            _msgs = self._messages(mode, plan, selected_tool_names=selected_tool_names,
                                    user_text=raw_text_early, route_context=(len(events) == 0))
            _messages_build_ms = round((time.perf_counter() - _messages_build_t0) * 1000.0, 3)
            # Re-resolve the router model per call: a tool may have injected an
            # image (e.g. screenshot) into history mid-turn, which forces the
            # vision preset even on a text-mode turn. See _messages_have_image.
            _call_model = self._router_model_for(_msgs)
            # SUMMARY-PASS slimming (latency). After a tool has run on
            # a SINGLE-ACTION turn (fast/quick_action), the next pass just
            # summarizes the result ("Listo, abrí Steam"). There, the tool-
            # schemas catalog is dead weight in the prefill (~800-1500 tokens)
            # and a 512-token cap is pointless for one sentence. Decode is
            # memory-bound at ~60 tok/s, so fewer prompt+output tokens = directly
            # less latency. Guards STRICTLY scoped so we never break multi-step:
            #   - only single-action modes (fast_action/quick_action), which are
            #     not expected to chain tools (deep/research/vision keep tools);
            #   - only after a tool ran (len(events)>0);
            #   - never when an image was injected (vision needs room + tools).
            # If a single-action turn somehow still wants another tool, the next
            # loop iteration is gone, but these modes are single-shot by design.
            # Honesty/grounding guards run on the reply text and are untouched.
            _is_summary_pass = (
                len(events) > 0
                and mode.name in {"fast_action", "quick_action"}
                and not _messages_have_image(_msgs)
            )
            # DESCRIBE-PASS (crítico no-vidente): tras inyectar una
            # imagen para DESCRIBIRLA (vision describe_screen / leer pantalla), el
            # 4B debe RESPONDER EN TEXTO la descripción — NO llamar más tools. Si
            # le dejamos tools, el modelo débil a veces elige session.cancel_turn
            # ("nada que describir") en vez de describir (medido). Quitamos las
            # tools y damos budget amplio para que narre. Es el camino que hace
            # la lectura de pantalla funcionar para alguien que no ve.
            _is_describe_pass = (len(events) > 0 and _messages_have_image(_msgs))
            # RESEARCH answer pass: after one evidence/search tool returned,
            # answer from that evidence instead of giving the model another
            # tool catalog. This keeps ordinary lookups inside the voice
            # latency budget and prevents weak-model tool loops, without
            # hardcoding any language or query.
            _is_research_answer_pass = (
                len(events) > 0
                and mode.name == "research"
                and not _messages_have_image(_msgs)
            )
            if _is_describe_pass:
                _pass_tools = None          # forzar respuesta en texto (descripción)
                _pass_max = max(mode.max_tokens, 512)
                _keep_summary_tools = False
            elif _is_research_answer_pass:
                _pass_tools = None
                _pass_max = min(mode.max_tokens, 320)
                _keep_summary_tools = False
            else:
                # SUMMARY slimming dropped tools to save ~1.5k prompt
                # tokens — but that CHANGES the prefix vs pass-1 and busts the
                # prefix-cache (measured: pass-2 re-prefills ~5.3k tok, ~1s). With
                # GEMMA4_SUMMARY_KEEP_TOOLS the prefix stays identical -> cache hit
                # (re-prefill only the ~50 new tool-result tokens). Net win if reuse
                # works. See PROMPT_RESEARCH_prefill_cache_latency.md.
                # Cache-hit mode (keep tools) ONLY after a clearly-SUCCESSFUL tool:
                # there the byte-identical prefix yields a cache hit (~1s). On FAILURE
                # the model re-engages with enable_thinking=True (measured runaway),
                # so we keep the ORIGINAL slim path (drop tools + thinking off) — no
                # cache hit but no runaway and no extra tokens. See compass / SPRINT.
                _last_res = getattr(events[-1], "result", {}) or {} if events else {}
                _last_ok = (
                    _last_res.get("verified") is True or _last_res.get("ok") is True
                    or str(_last_res.get("status") or "").lower() in {"ok", "success", "dispatched"}
                )
                _keep_summary_tools = (
                    _is_summary_pass and _summary_keep_tools_enabled() and _last_ok
                )
                _pass_tools = None if (_is_summary_pass and not _keep_summary_tools) else selected_schemas
                _pass_max = 160 if _is_summary_pass else mode.max_tokens
            # Split (FunctionGemma router): el E2B NO recibe los schemas nativos —
            # FG decide la tool, el E2B (QAT) solo conversa/narra. Pasarle tools=[] al
            # E2B solo infla el prompt ~1.7k tokens (schemas vía --jinja) y lo desborda
            # del ctx (MEDIDO 2026-06-17: "abre Steam" 7002 > 6144 -> 400; con tools=None
            # el prompt de acción cae a ~base ~5.3k y entra). El _greedy/few-shot de
            # tool-call quedan inertes a propósito: el tool-call lo hace FG, no el E2B.
            if _fg_router_on() and _pass_tools is not None:
                _pass_tools = None
            # CACHE-HIT (research compass): keeping the tools is NOT enough
            # to hit the prefix cache — pass-1 rendered the prompt with
            # enable_thinking=mode.enable_thinking, and if the summary TOGGLES it the
            # chat template re-renders from token ~0 and the cache fully misses
            # (MEASURED cache_n=4). _keep_summary_tools is already success-gated above
            # (enable_thinking=True makes the model re-engage with a FAILED action ->
            # runaway, so failures use the slim+thinking-off path). On success: match
            # pass-1's enable_thinking (byte-identical prefix -> cache HIT) with a
            # minimal thinking_budget (16; budget is a body sampler param, NOT part of
            # chat_template_kwargs, so it doesn't affect the cached prefix — and a tiny
            # budget avoids the budget-0 mid-think cut that also misbehaved).
            if _keep_summary_tools:
                _pass_enable_thinking = mode.enable_thinking
                _pass_thinking_budget = 16
            else:
                _pass_enable_thinking = _think_now
                _pass_thinking_budget = mode.thinking_budget
            # SAMPLING DUAL (inv 1): greedy en el turno de ACCIÓN
            # (hay tools ofrecidas, ninguna corrió aún, y NO es summary-pass) ->
            # decisión de tool-call con baja entropía, más fiable sin reasoning.
            # En summary-pass / conversación NO greedy (necesita lenguaje natural).
            _greedy = bool(_pass_tools) and len(events) == 0 and not _is_summary_pass
            # FEW-SHOT DINÁMICO de acción (2026-06-10): en el turno de acción
            # (greedy), antepone 1-2 pares (user ejemplo -> assistant tool_call) de
            # las tools que el router ofrece, en formato nativo. Ataca el
            # "first-token misalignment" que causa el residual de tool-call (~75%
            # en vivo): sesga el primer token a DISPARAR la tool en vez de narrar.
            # Mensajes OpenAI normales (el chat_template los renderiza a nativo).
            # NO es respuesta enlatada: el LLM sigue decidiendo. Inserta antes del
            # último user (el pedido real). Gate GEMMA4_ACTION_FEWSHOT=0.
            # Ver routing/action_fewshot.py + research/1_toolcalling.md.
            if _greedy:
                try:
                    from gemma4_agent.routing.action_fewshot import build_action_fewshot
                    _fewshot = build_action_fewshot(selected_tool_names)
                    if _fewshot:
                        _ins = len(_msgs)
                        while _ins > 0 and _msgs[_ins - 1].get("role") == "user":
                            _ins -= 1
                        _msgs = _msgs[:_ins] + _fewshot + _msgs[_ins:]
                except Exception:
                    pass
            # STREAMING TTS (GEMMA4_STREAM_TTS, default off). Two safe cases:
            #  - SUMMARY pass (events>0): the content-REPLACING guards are provably
            #    pass-through (grounding_gate.py:206, agent_guards.py:253) -> stream
            #    the confirmation freely.
            #  - INFO pass (events==0, fast_info): the reply is generated in one pass
            #    (no pass-1+execute pre-wait) so streaming wins more; the claim guards
            #    CAN fire here, so _chat_streaming runs the REAL detectors per
            #    increment and ABORTS before voicing anything a guard would replace
            #    (guard_check=True). Both require thinking OFF (no <think> in the
            #    stream) and no routine (phrase_confirm PREPENDS). If the info pass
            #    emits a tool_call instead of prose, no content is streamed (harmless;
            #    the turn proceeds as an action). See SPRINT_streaming_tts_truthful.md.
            _stream_this = (
                getattr(self, "_active_tts_sink", None) is not None
                and not getattr(self, "_phrase_fires", None)
                and _stream_tts_enabled()
                and not _think_now
                and not _is_describe_pass
                and (_is_summary_pass or (len(events) == 0 and mode.name == "fast_info"))
            )
            try:
                _messages_chars = sum(len(str(m.get("content") or "")) for m in _msgs)
                _tools_chars = sum(len(json.dumps(s)) for s in (_pass_tools or []))
                _since_llm_start_ms = round(
                    (time.perf_counter() - getattr(self, "_turn_perf_t0", time.perf_counter())) * 1000.0,
                    3,
                )
                self.trace.event(
                    turn_id,
                    "llm_call_start",
                    turn=_turn + 1,
                    model=_call_model,
                    mode=mode.name,
                    events=len(events),
                    tools_sent=len(_pass_tools or []),
                    messages_chars=_messages_chars,
                    tools_chars=_tools_chars,
                    messages_build_ms=_messages_build_ms,
                    thinking=bool(_pass_enable_thinking),
                    thinking_budget=_pass_thinking_budget,
                    max_tokens=_pass_max,
                    summary_pass=bool(_is_summary_pass),
                    describe_pass=bool(_is_describe_pass),
                    research_answer_pass=bool(_is_research_answer_pass),
                    stream=bool(_stream_this),
                    since_turn_start_ms=_since_llm_start_ms,
                )
                _progress(
                    progress,
                    "llm_start",
                    since_turn_start_ms=_since_llm_start_ms,
                    tools_sent=len(_pass_tools or []),
                    messages_chars=_messages_chars,
                    mode=mode.name,
                )
            except Exception:
                pass
            _llm_wall_t0 = time.perf_counter()
            try:
                if _stream_this:
                    try:
                        resp = self._chat_streaming(
                            # tools=None: a streamed pass is PURE PROSE. For the
                            # info pass this is the truthfulness keystone — with no
                            # tool offered the model answers from knowledge and the
                            # turn CANNOT spawn a later tool+summary that would
                            # supersede (and silently replace) what we already
                            # voiced. The summary pass already uses tools=None.
                            _msgs, model=_call_model, max_tokens=_pass_max,
                            thinking_budget=mode.thinking_budget,
                            timeout_s=mode.request_timeout_s, turn_id=turn_id,
                            tools=None, enable_thinking=_think_now,
                            greedy=_greedy,
                            sampling={"temperature": mode.temperature,
                                      "top_p": mode.top_p, "top_k": mode.top_k},
                            guard_check=(len(events) == 0),
                        )
                    except Exception as _stream_exc:  # noqa: BLE001
                        # Streaming failed mid-flight -> fall back to the blocking
                        # call (truthful, just slower). tts_streamed reset so the
                        # runner re-feeds the full reply; any clean prose already
                        # queued may briefly repeat (rare error path, not a lie).
                        self.trace.event(turn_id, "tts_stream_fallback", error=str(_stream_exc))
                        self._tts_streamed = False
                        self._tts_streamed_text = ""
                        resp = self.client.chat(
                            _msgs, tools=_pass_tools, enable_thinking=_think_now,
                            thinking_budget=mode.thinking_budget, model=_call_model,
                            parallel_tool_calls=mode.parallel_tool_calls,
                            max_tokens=_pass_max, greedy=_greedy,
                            sampling={"temperature": mode.temperature, "top_p": mode.top_p,
                                      "top_k": mode.top_k},
                            timeout_s=mode.request_timeout_s,
                        )
                else:
                    resp = self.client.chat(
                        _msgs,
                        tools=_pass_tools,
                        enable_thinking=_pass_enable_thinking,
                        thinking_budget=_pass_thinking_budget,
                        model=_call_model,
                        parallel_tool_calls=mode.parallel_tool_calls,
                        max_tokens=_pass_max,
                        greedy=_greedy,
                        # SAMPLING POR MODO (inv 0 T4): baja-T en modos de acción/info
                        # breve. Greedy gana sobre esto en el turno de tool-call.
                        sampling={"temperature": mode.temperature, "top_p": mode.top_p,
                                  "top_k": mode.top_k},
                        # Per-mode deadline so a hung/slow call fails fast instead of
                        # blocking up to the global 180s * max_agent_turns. Derived
                        # from the token budget (see AgentMode.request_timeout_s).
                        timeout_s=mode.request_timeout_s,
                    )
            except Exception as exc:
                try:
                    self.trace.event(
                        turn_id,
                        "llm_call_error",
                        turn=_turn + 1,
                        wall_ms=round((time.perf_counter() - _llm_wall_t0) * 1000.0, 3),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                except Exception:
                    pass
                if _looks_like_context_overflow(str(exc)):
                    _progress(progress, "context_retry", error=str(exc), tools=len(events))
                    self.trace.event(turn_id, "context_retry", error=str(exc), tool_events=len(events))
                    self._compact_active_history_for_retry()
                    # Drop the lowest-priority half of the subset, keeping at
                    # least 4. The planner already orders by priority (utility
                    # tools last), so this preserves the most relevant ones.
                    original_count = len(selected_tool_names)
                    keep_count = max(4, original_count // 2)
                    retry_tool_names = selected_tool_names[:keep_count]
                    selected_tool_names = retry_tool_names  # propagar al system prompt tambien
                    self.trace.event(turn_id, "subset_truncate_retry", original=original_count, kept=len(retry_tool_names))
                    selected_schemas = self.tools.schemas_for_names(retry_tool_names)
                    _msgs_r = self._messages(mode, plan, selected_tool_names=selected_tool_names, user_text=raw_text_early)
                    try:
                        resp = self.client.chat(
                            _msgs_r,
                            tools=(None if _fg_router_on() else selected_schemas),
                            enable_thinking=mode.enable_thinking,
                            thinking_budget=mode.thinking_budget,
                            model=self._router_model_for(_msgs_r),
                            parallel_tool_calls=mode.parallel_tool_calls,
                            max_tokens=mode.max_tokens,
                            timeout_s=mode.request_timeout_s,
                        )
                    except Exception as retry_exc:
                        _progress(progress, "error", error=str(retry_exc), tools=len(events))
                        self.trace.event(turn_id, "llm_error", error=str(retry_exc), tool_events=len(events), after_context_retry=True)
                        self._last_turn_ts = time.time()
                        return AgentReply(content="", tool_events=events, error=str(retry_exc))
                    else:
                        self.trace.event(turn_id, "context_retry_ok", schema_count=len(selected_schemas))
                        _progress(progress, "context_retry_ok", tools=len(events), schema_count=len(selected_schemas))
                else:
                    _progress(progress, "error", error=str(exc), tools=len(events))
                    self.trace.event(turn_id, "llm_error", error=str(exc), tool_events=len(events))
                    self._last_turn_ts = time.time()
                    return AgentReply(content="", tool_events=events, error=str(exc))

            _llm_wall_ms = round((time.perf_counter() - _llm_wall_t0) * 1000.0, 3)
            choice = (resp.get("choices") or [{}])[0]
            raw_msg = choice.get("message") or {}
            msg = sanitize_assistant_message(raw_msg)
            assistant_content = msg.get("content") or ""
            raw_tool_calls = msg.get("tool_calls") or []
            # FunctionGemma run9 como router de tool-calling: si está activo, FunctionGemma
            # (270M, :8082) decide el tool-call en vez del E2B. El E2B ya corrió arriba (su
            # content queda para el caso conversacional); acá OVERRIDE-amos su DECISIÓN de tool.
            #   no_tool        -> abstención: raw_tool_calls=[] (responde el E2B conversacional).
            #   tool elegido   -> raw_tool_calls=[ese] (traducido a tool COMPUESTO de Baxy).
            #   FG no resolvió -> se queda la decisión del E2B (fallback). Gate GEMMA4_FG_ROUTER.
            if _fg_router_on() and not events and not getattr(self, "_fg_router_done", False):
                self._fg_router_done = True
                try:
                    from ..routing.fg_router import fg_emit
                    # e2b_emitted: 2ª señal del gate (el E2B abstiene perfecto en chitchat;
                    # si emitió tool, el turno es accionable aunque el encoder no pique).
                    _fg_name, _fg_args, _fg_missing = fg_emit(raw_text_early, e2b_emitted=bool(raw_tool_calls))
                    # COMPLETAR ARGS FALTANTES con el LLM de habla: FG-270M a veces devuelve el tool
                    # sin uno o VARIOS de sus valores (MEDIDO: "abre Steam"->app.open sin name; "pon X
                    # en spotify"->play sin query NI provider — perdía la plataforma). El QAT (2B, con
                    # TODO el contexto del turno) extrae cada campo del texto del usuario. Si el usuario
                    # NO lo dijo ("abre" a secas, "poné una canción" sin título), el QAT devuelve None
                    # por ese campo y NO se completa: honestidad, no se inventa el valor. Solo corre
                    # sobre los faltantes reales (cap 3 en fg_emit) -> latencia acotada.
                    if (_fg_name and _fg_name != "no_tool" and _fg_missing and isinstance(_fg_args, dict)):
                        _action = str(_fg_args.get("action") or "")
                        for _field in _fg_missing:
                            if _fg_args.get(_field):
                                continue
                            _val = self._fg_complete_arg(raw_text_early, _fg_name, _action, _field)
                            if _val:
                                _fg_args[_field] = _val
                                self.trace.event(turn_id, "fg_arg_completed",
                                                 tool=_fg_name, field=_field, value=_val)
                    self.trace.event(turn_id, "fg_router", tool=_fg_name, args=_fg_args)
                    if _fg_name == "no_tool":
                        raw_tool_calls = []
                    elif _fg_name:
                        raw_tool_calls = [{"id": "fg1", "type": "function", "function": {
                            "name": _fg_name,
                            "arguments": json.dumps(_fg_args or {}, ensure_ascii=False)}}]
                        msg = {"role": "assistant", "content": "", "tool_calls": raw_tool_calls}
                        assistant_content = ""
                except Exception as _fg_exc:
                    self.trace.event(turn_id, "fg_router_error",
                                     error=f"{type(_fg_exc).__name__}: {_fg_exc}")
            # DEDUP DE BATCH DEGENERADO (bug Gemma 4 lmstudio #1756, medido en
            # cacería tanda 1): el 4B emite el MISMO tool_call decenas de veces en
            # UNA respuesta, ignorando parallel_tool_calls=false. "Investiga en
            # internet que es el h2o" -> 72 calls que colapsan a 5 únicos; ~30s de
            # decode + re-alimentación del history. Colapsamos duplicados exactos
            # y capamos a MAX_TOOL_CALLS_PER_RESPONSE distintas ANTES de ejecutar,
            # cortando la amplificación del loop. Estructural (mide la FORMA, no el
            # contenido). Gate GEMMA4_BATCH_DEDUP_OFF=1 lo apaga. Sincronizamos msg
            # para que el history que va al LLM refleje lo realmente ejecutado.
            if len(raw_tool_calls) > 1:
                from ..safety_pkg.loop_detection import dedup_degenerate_batch
                _deduped, _dd_info = dedup_degenerate_batch(raw_tool_calls)
                if _dd_info["kept"] < _dd_info["original"]:
                    raw_tool_calls = _deduped
                    msg["tool_calls"] = _deduped
                    self.trace.event(
                        turn_id, "batch_dedup",
                        original=_dd_info["original"],
                        kept=_dd_info["kept"],
                        dropped_duplicates=_dd_info["dropped_duplicates"],
                        dropped_over_cap=_dd_info["dropped_over_cap"],
                    )
            # Extract optional <intent> tag from content (validator). The tag
            # is stripped from the visible reply but kept on the side so the
            # tool-selection validator can compare declared intent vs chosen
            # (tool, action) pair below.
            from ..safety_pkg.intent_validator import (
                corrective_message,
                extract_intent_tag,
                strip_intent_tag,
                validate_call,
            )
            intent_tag = extract_intent_tag(assistant_content)
            if intent_tag is not None:
                assistant_content = strip_intent_tag(assistant_content)
                msg["content"] = assistant_content
                self.trace.event(turn_id, "intent_tag_extracted",
                                 intent_type=intent_tag.intent_type,
                                 target=intent_tag.target[:120])
            if raw_tool_calls and assistant_content:
                self.trace.event(
                    turn_id,
                    "pre_tool_content_discarded",
                    content=(assistant_content or "")[:200],
                    tool_call_count=len(raw_tool_calls),
                )
                assistant_content = ""
                msg["content"] = ""
            # RESCATE ESTRUCTURAL de leaked-call (forma, no keyword): el modelo a veces
            # emite el tool-call como TEXTO Python-style `name(action="val")` en vez del
            # formato nativo <|tool_call> que el parser extrae -> el call se pierde y el
            # TEXTO leakea como respuesta hablada (MEDIDO en vivo 2026-06-18: "qué día es"
            # garbleado -> FG abstiene -> el QAT con tools=None escupe `system(action='time')`
            # y eso quedaba como reply). detect_leaked_tool_call lo re-parsea a un tool-call
            # real (solo dispara si el nombre es un tool conocido). SIEMPRE activo, también en
            # modo neto: es ESTRUCTURAL (mide la forma, no el contenido) — CLAUDE.md permite
            # guardas estructurales aun con GEMMA4_GUARDS=0; el neto saca los guards de
            # COMPORTAMIENTO, no la recuperación de un tool-call malformado.
            if not raw_tool_calls and assistant_content:
                try:
                    from ..tools_pkg.tools import COMPOUND_TOOL_SCHEMAS as _CTS, ACTION_ENUMS as _AE
                    _known = {s["function"]["name"] for s in _CTS
                              if isinstance(s, dict) and isinstance(s.get("function"), dict)
                              and isinstance(s["function"].get("name"), str)}
                    _amap = build_action_to_tool(_known, _AE)
                    _rescued = detect_leaked_tool_call(assistant_content, known_tool_names=_known,
                                                       action_to_tool=_amap)
                    if _rescued is not None:
                        raw_tool_calls = [_rescued]
                        assistant_content = ""
                        msg = {"role": "assistant", "content": "", "tool_calls": raw_tool_calls}
                        self.trace.event(turn_id, "tool_call_rescued",
                                         tool=_rescued["function"]["name"])
                except Exception:
                    pass
            # HÍBRIDO (rama Experimentando, conclusión del experimento): se removió
            # TODO el guard-stack salvo este forced_tool_retry MÍNIMO. Medido: el FT
            # NO cubre el under-action (~12% es; oversample no lo mueve, techo del E2B),
            # pero ESTE retry sí (era load-bearing — al sacarlo apareció el under-action).
            # NÚCLEO solo: si el LLM no emitió tool-call y había tool de DOMINIO ofrecida
            # y no se ejecutó nada aún -> UN reintento con tool_choice=required. SIN las
            # heurísticas del guard original (deterministic nets, info-skip, semantic-
            # fallback, leaked-call rescue): solo el núcleo que la medición justificó.
            # Gate GEMMA4_FORCED_TOOL_RETRY=0.
            import os as _os_fr0
            if (_GUARDS_ON and not raw_tool_calls and selected_schemas and len(events) == 0
                    and not getattr(self, "_forced_tool_retry_done", False)
                    and _os_fr0.environ.get("GEMMA4_FORCED_TOOL_RETRY", "1").strip().lower()
                        not in {"0", "false", "no", "off"}):
                try:
                    from .agent_helpers import _domain_subset
                    _domain_now = _domain_subset(list(selected_tool_names))
                except Exception:
                    _domain_now = [t for t in selected_tool_names
                                   if t not in ("session", "safety", "state", "verify")]
                if _domain_now:
                    self._forced_tool_retry_done = True
                    self.trace.event(turn_id, "forced_tool_retry", domain_subset=_domain_now,
                                     skipped_reply=(assistant_content or "")[:120])
                    _progress(progress, "forced_tool_retry", tools=len(events))
                    try:
                        _msgs_fr = self._messages(mode, plan, selected_tool_names=selected_tool_names,
                                                  user_text=raw_text_early)
                        _cap = mode.max_tokens
                        if isinstance(_cap, int):
                            _cap = min(_cap, 128)  # cap anti-ramble (medido en el guard original)
                        _resp_fr = self.client.chat(
                            _msgs_fr, tools=selected_schemas, enable_thinking=mode.enable_thinking,
                            thinking_budget=mode.thinking_budget, model=self._router_model_for(_msgs_fr),
                            parallel_tool_calls=mode.parallel_tool_calls, max_tokens=_cap,
                            timeout_s=mode.request_timeout_s, force_tool=True)
                        _msg_fr = sanitize_assistant_message((_resp_fr.get("choices") or [{}])[0].get("message") or {})
                        _tc_fr = _msg_fr.get("tool_calls") or []
                        if _tc_fr:
                            raw_tool_calls = _tc_fr
                            msg = _msg_fr
                            assistant_content = ""
                            self.trace.event(turn_id, "forced_tool_retry_success", tools=len(_tc_fr))
                        else:
                            self.trace.event(turn_id, "forced_tool_retry_empty")
                    except Exception as _fr_exc:
                        self.trace.event(turn_id, "forced_tool_retry_error",
                                         error=f"{type(_fr_exc).__name__}: {_fr_exc}")

            # PERF instrumentation (research/latency/prefill_*.md
            # Punto 1 "Como medir"): el campo timings.cache_n / prompt_n del
            # response de llama-server expone el prefix-cache real. cache_n =
            # tokens reusados; prompt_n = reprocesados. Meta: hit_ratio >= 0.80
            # p50, >= 0.60 p90. Si baja, el prefijo se esta rompiendo (debug
            # con bit-a-bit diff de dos turnos consecutivos).
            _timings = (resp.get("timings") if isinstance(resp, dict) else None) or {}
            _usage = (resp.get("usage") if isinstance(resp, dict) else None) or {}
            _server_ms = None
            if _timings.get("prompt_ms") is not None or _timings.get("predicted_ms") is not None:
                _server_ms = float(_timings.get("prompt_ms") or 0) + float(_timings.get("predicted_ms") or 0)
            self.trace.event(
                turn_id,
                "llm_response",
                finish_reason=choice.get("finish_reason"),
                content_chars=len(assistant_content),
                tool_call_count=len(raw_tool_calls),
                stripped_reasoning=any(k in raw_msg for k in ("reasoning", "reasoning_content", "reasoning_details")),
                # Prefill telemetry (campos opcionales — solo si el server los expone)
                cache_n=_timings.get("cache_n"),
                prompt_n=_timings.get("prompt_n"),
                prompt_ms=_timings.get("prompt_ms"),
                predicted_n=_timings.get("predicted_n"),
                predicted_ms=_timings.get("predicted_ms"),
                prompt_tokens=_usage.get("prompt_tokens"),
                cached_tokens=(_usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                wall_ms=_llm_wall_ms,
                server_ms=round(_server_ms, 3) if _server_ms is not None else None,
                client_overhead_ms=(
                    round(_llm_wall_ms - _server_ms, 3) if _server_ms is not None else None
                ),
                messages_build_ms=_messages_build_ms,
            )
            _progress(
                progress,
                "llm_response",
                turn=_turn + 1,
                tool_calls=len(raw_tool_calls),
                tools=len(events),
            )

            if not raw_tool_calls:
                # finalize (~500 LOC de post-procesamiento
                # del reply sin tool calls) extraída a _finalize_turn. Devuelve
                # AgentReply o el sentinel _FINALIZE_CONTINUE (que el caller
                # traduce a `continue` del for _turn).
                _fin_result = self._finalize_turn(
                    content, assistant_content, events, msg,
                    raw_text_early, turn_id, verifier_outcomes, mission_goal,
                    plan, selected_tool_names, progress, mode=mode,
                )
                if _fin_result is _FINALIZE_CONTINUE:
                    continue
                return _fin_result

            # Validator: if the LLM declared an <intent> and chose a tool
            # that is on the reject list for that intent, reject and retry
            # once. We only check the FIRST tool call — parallel multi-tool
            # turns are rare for the ambiguous-subset case.
            if intent_tag is not None and raw_tool_calls:
                first = raw_tool_calls[0]
                fn0 = first.get("function") or {}
                first_args, _ = _parse_args(fn0.get("arguments", {}))
                v = validate_call(intent_tag, fn0.get("name", ""), first_args)
                if v.rejected and validator_retries_used == 0:
                    self.trace.event(
                        turn_id, "validator_rejected",
                        declared_intent=v.declared_intent,
                        chosen_tool=v.chosen_tool,
                        chosen_action=v.chosen_action,
                        reason=v.reason,
                    )
                    validator_retries_used += 1
                    self.history.append({
                        "role": "user",
                        "content": corrective_message(v),
                    })
                    continue
                if v.rejected:
                    self.trace.event(
                        turn_id, "validator_gave_up",
                        declared_intent=v.declared_intent,
                        chosen_tool=v.chosen_tool,
                        chosen_action=v.chosen_action,
                        reason=v.reason,
                    )
                else:
                    self.trace.event(
                        turn_id, "validator_passed",
                        declared_intent=v.declared_intent,
                        chosen_tool=v.chosen_tool,
                        chosen_action=v.chosen_action,
                    )

            self.history.append(msg)

            image_results: list[tuple[Path, dict[str, Any], str]] = []
            subset_set = set(selected_tool_names)

            # Phase 1: parse + classify all calls (no execution yet).
            prepared: list[dict[str, Any]] = []
            for raw_call in raw_tool_calls:
                fn = raw_call.get("function") or {}
                name = fn.get("name", "")
                args, parse_error = _parse_args(fn.get("arguments", {}))
                # AUTO-REPAIR de path (informe B): el modelo (E4B,4B)
                # encadena search->open pero llama office.open / media.play /
                # filesystem.read con path AUSENTE o inválido (no copia el
                # resultado del search). En vez de fallar "ruta no válida",
                # rellenamos el path con el PRIMER resultado del filesystem.search
                # exitoso más reciente del turno. Determinista, NO ejecuta una
                # tool que el LLM no eligió — solo repara su argumento. Bug #847.
                if isinstance(args, dict) and not parse_error:
                    repaired = self._autorepair_path_from_search(name, args, events)
                    if repaired is not None:
                        self.trace.event(turn_id, "path_autorepaired",
                                         tool=name, path=repaired)
                        args = {**args, "path": repaired}
                    if (
                        mode.name == "research"
                        and name == "web"
                        and str(args.get("action") or "").casefold() == "research"
                        and _research_fast_search_enabled()
                        and not _should_keep_full_web_research(raw_text_early, args)
                    ):
                        args = {
                            **args,
                            "action": "search",
                            "limit": int(args.get("limit", 3) or 3),
                            "timeout_sec": int(args.get("timeout_sec", 4) or 4),
                        }
                        self.trace.event(
                            turn_id,
                            "web_research_fast_search",
                            query=str(args.get("query") or "")[:160],
                        )
                in_subset = name in subset_set
                self.trace.event(turn_id, "tool_call", name=name, args=args, in_subset=in_subset, parse_error=parse_error)
                # B3b: earcon de progreso NO-VERBAL antes de una tool LENTA (web/visión/
                # ~3s). Reemplaza el "buscando…" hablado (viola "nada enlatado"). Gated
                # GEMMA4_PROGRESS_EARCON (default-off), best-effort, non-blocking, throttled.
                try:
                    from ..voice.earcon import SLOW_TOOLS as _slow_earcon, play_progress_earcon
                    if name in _slow_earcon:
                        play_progress_earcon()
                except Exception:
                    pass
                if not in_subset:
                    self.trace.event(turn_id, "router_miss", name=name, sent=sorted(subset_set))
                # Hotfix I: pre-dispatch safety hook for
                # purchase / paid-action attempts. Inspects args
                # for checkout-pattern URLs and known paid action
                # names. When safety_enabled, a hit pre-loads a
                # synthetic needs_confirmation result so the
                # dispatcher skips the real call. When safety is
                # off, only the trace event fires.
                _pre_dispatch_result: dict[str, Any] | None = None
                # Rama Experimentando: SIN safety_hook (no se bloquean compras/
                # acciones-pagas pre-dispatch). _pre_dispatch_result queda None ->
                # la tool se ejecuta sin gate de confirmación.
                # EAGER read-only (opt-in): si pre-ejecutamos esta lectura en
                # background (en _decide_turn, en paralelo al pase-1) y el LLM la
                # pidió tal cual (read-only, sin args con efectos), servimos el
                # resultado YA listo en vez de re-ejecutar la tool — ahorra su
                # latencia. SOLO si NO hubo parse-error NI un pre-block de safety
                # (safety SIEMPRE gana). El get() re-verifica eager-safety contra
                # los args REALES del LLM: una variante con efectos NO se sirve.
                # Fail-safe: cache miss/None -> dispatch normal corre la tool.
                if (_pre_dispatch_result is None and not parse_error
                        and getattr(self, "_eager_cache", None) is not None
                        and isinstance(args, dict)):
                    try:
                        _eager_action = str(args.get("action") or "")
                        _eager_hit = self._eager_cache.get(name, _eager_action, args)
                    except Exception:
                        _eager_hit = None
                    if isinstance(_eager_hit, dict):
                        _pre_dispatch_result = _eager_hit
                        try:
                            self.trace.event(turn_id, "eager_readonly_hit",
                                             tool=name, action=_eager_action)
                        except Exception:
                            pass
                prepared.append({
                    "raw_call": raw_call,
                    "name": name,
                    "args": args,
                    "parse_error": parse_error,
                    "_pre_dispatch_result": _pre_dispatch_result,
                })

            # Phase 2: execute. Parallel when enabled, multiple valid calls
            # and the LLM did not request a strict order.
            parallel_ok = _parallel_tools_enabled() and sum(1 for p in prepared if not p["parse_error"]) >= 2
            _tools_batch_t0 = time.perf_counter()
            if parallel_ok:
                self.trace.event(turn_id, "tools_parallel_start", count=len(prepared))
                self._execute_calls_parallel(prepared, progress, len(events), turn_id=turn_id)
            else:
                self._execute_calls_sequential(prepared, progress, len(events), turn_id=turn_id)
            self.trace.event(
                turn_id,
                "tools_batch_done",
                count=len(prepared),
                parallel=bool(parallel_ok),
                wall_ms=round((time.perf_counter() - _tools_batch_t0) * 1000.0, 3),
            )

            # Phase 3: apply results in original order to events, history,
            # traces, failure log, image collection.
            for prep in prepared:
                name = prep["name"]
                args = prep["args"]
                raw_call = prep["raw_call"]
                result = prep.get("result") or {}
                events.append(ToolEvent(name=name, args=args, result=result))
                self.trace.event(turn_id, "tool_result", name=name, result=result)
                # JARVIS (inv 5): registrar acciones del usuario para detectar
                # rutinas. Solo app open/close EXITOSAS (señal estable). Best-
                # effort; nunca rompe el turno.
                if self.behavior is not None and isinstance(result, dict) and result.get("ok"):
                    try:
                        _act = str(args.get("action") or "").casefold()
                        _nm = str(args.get("name") or args.get("app") or "").strip()
                        if name == "app" and _act in ("open", "close") and _nm:
                            self.behavior.record(f"app_{_act}", _nm)
                    except Exception:
                        pass
                # Surface which skill the LLM loaded so usage reports
                # can answer "which skills earn their spot in the menu?".
                # (No skill_load activity was observed in 6727 events.)
                if name == "skill_load" and isinstance(result, dict) and result.get("ok"):
                    self.trace.event(
                        turn_id, "skill_loaded",
                        name=str(result.get("skill") or args.get("name") or ""),
                        chars=int(result.get("chars") or 0),
                    )
                # Loop detector: record y check antes de seguir con la siguiente
                # tool de este batch. exists=True salvo que el result diga
                # "unknown tool" en el error (tool no registrada). El detector
                # filtra timestamps/pids del result_sig para no confundir polling
                # legitimo con loop.
                err_str = str(result.get("error") or "")
                tool_exists = not err_str.startswith("unknown tool:")
                loop_state.record(name, args, exists=tool_exists, result=result)

                # RED DE SEGURIDAD batch-aware (BUG real medido): un 4B puede emitir
                # un batch DEGENERADO de 100+ tool_calls en UNA sola respuesta. El
                # detect_stuck() de abajo corre UNA vez por turno (tras el batch) ->
                # las 140 ya se ejecutaron antes de que el circuit breaker mire. Acá
                # cortamos el batch en cuanto el contador global cruza el umbral, así
                # un solo response no puede disparar 100+ acciones físicas. break del
                # batch -> el detect_stuck post-loop ve el critical y aborta el turn.
                if loop_state.global_count >= _LOOP_CIRCUIT_BREAKER:
                    self.trace.event(turn_id, "batch_circuit_breaker",
                                     executed=loop_state.global_count,
                                     batch_size=len(prepared))
                    loop_aborted = True
                    break

                # Rama Experimentando: SIN verifiers estructurales (no se mide el
                # efecto post-ejecución ni se infla mission con confirmed). Solo se
                # actualiza el tracking de misión por el ok crudo del result.
                mission_goal.update_with_tool(name, args, bool(result.get("ok")))
                if not result.get("ok"):
                    status_norm = str(result.get("status") or "").casefold()
                    completion = str(result.get("completion_status") or "").casefold()
                    is_blocked = (
                        status_norm.startswith("needs_")
                        or completion.startswith("needs_")
                    )
                    if not is_blocked:
                        failure_log.append({"step": len(events), "tool": name, "error": str(result.get("error") or "")[:300]})
                    else:
                        self.trace.event(turn_id, "failure_excluded_from_replan", tool=name, status=status_norm, completion=completion)

                # Hotfix F: pending_intent cross-turn rescue.
                # When a tool returns status='needs_user' (a structural
                # signal — never inferred from text), stash the intent
                # so the next turn's router has a hint regardless of
                # how the user phrases their reply. Cleared below when
                # the same tool runs successfully.
                _status_norm = str(result.get("status") or "").casefold()
                if _status_norm == "needs_user" and hasattr(self.state, "set_pending_intent"):
                    asks_for = str(
                        result.get("asks_for")
                        or result.get("missing")
                        or "user_input"
                    )
                    self.state.set_pending_intent(
                        tool=name,
                        args=dict(args or {}),
                        asks_for=asks_for,
                        current_turn=self._turn_counter,
                    )
                    self.trace.event(
                        turn_id, "pending_intent_set",
                        tool=name, asks_for=asks_for,
                    )
                elif (
                    pending_intent
                    and pending_intent.get("tool") == name
                    and not _is_unverified_result(result)
                    and hasattr(self.state, "clear_pending_intent")
                ):
                    self.state.clear_pending_intent()
                    self.trace.event(
                        turn_id, "pending_intent_cleared", tool=name,
                    )

                # Hotfix I: pending_question slot. The
                # tool ran but emitted clarification_needed (or
                # partial_reason). Separate slot from pending_intent
                # because the semantics differ — "ran-but-partial"
                # vs "about-to-run". The router consumes both via
                # the same pending_tool_hint kwarg downstream.
                _clarif = result.get("clarification_needed") or result.get("partial_reason")
                if (
                    isinstance(_clarif, str) and _clarif
                    and hasattr(self.state, "set_pending_question")
                ):
                    self.state.set_pending_question(
                        tool=name,
                        question_topic=_clarif,
                        last_args=dict(args or {}),
                        current_turn=self._turn_counter,
                    )
                    self.trace.event(
                        turn_id, "pending_question_set",
                        tool=name, question_topic=_clarif,
                    )
                _progress(
                    progress,
                    "tool_end",
                    name=name,
                    ok=bool(result.get("ok")),
                    status=str(result.get("status") or ""),
                    verified=result.get("verified"),
                    index=len(events),
                )
                self.history.append({
                    "role": "tool",
                    "tool_call_id": raw_call.get("id", f"call_{name}"),
                    "content": json.dumps(_compact_tool_result(name, args, result), ensure_ascii=False),
                })

                image_path = result.get("image_path")
                if image_path:
                    image_results.append((Path(str(image_path)), result, name))

            for image_path, result, _img_tool in image_results:
                # Only feed the image to the LLM when the turn is genuinely
                # VISUAL — i.e. a vision mode, or the image came from a
                # vision/screenshot tool whose deliverable IS the picture.
                #
                # Regresión (minada de traces): action tools like
                # `media`/`browser` (play music/video) attach a self-VERIFICATION
                # screenshot (`screenshot is provided for visual verification`,
                # a 3840x1944 / 1.7 MB capture). That image is for the verifier,
                # not for the reply. Injecting it forced the follow-up reply pass
                # to the vision preset; when the running server didn't advertise
                # <profile>-vision the image landed on -text → HTTP 500 "image
                # input is not supported". A "Listo, abrí YouTube" confirmation
                # never needs to SEE the screenshot — so don't inject it.
                if not self._image_is_for_llm(mode, _img_tool, result):
                    self.trace.event(
                        turn_id, "tool_image_not_injected",
                        tool=_img_tool, reason="action_self_verification_screenshot",
                    )
                    continue
                # PRE-FLIGHT de VRAM
                # antes de inyectar una imagen capturada A MITAD de turno. El
                # pre-flight de _decide_turn solo corre para mode=='vision_action'
                # (imagen de ENTRADA); una imagen pedida por el LLM inline (un
                # gui.screenshot en un turno de texto) fuerza el preset de visión
                # -> carga mmproj (~946 MiB) -> OOM/zombie en 4GB SIN chequeo.
                # Acá el watchdog ACTÚA (no solo loguea): si no es seguro, reciclar;
                # si sigue inseguro, NO inyectar y dejar una nota honesta para el
                # LLM (mejor "no pude verla" que petar el server). Sin GPU NVIDIA
                # el watchdog es no-op (vision_safe()=True) -> no cambia nada.
                if not self._image_inject_vram_safe(turn_id):
                    self.history.append({
                        "role": "user",
                        "content": (
                            "[system note] No pude analizar la imagen visualmente: "
                            "la VRAM está demasiado ocupada para cargar el modelo de "
                            "visión sin arriesgar un crash. Respondé con lo que ya "
                            "sabés del texto/estado, o pedile al usuario que libere "
                            "memoria. NO inventes lo que habría en la imagen."
                        ),
                    })
                    self.trace.event(
                        turn_id, "tool_image_not_injected",
                        tool=_img_tool, reason="vram_unsafe_for_vision_inline")
                    continue
                _progress(progress, "image_injected", path=str(image_path))
                self._inject_tool_image(image_path, result)

            # Honesty guard: if any tool in the just-processed batch returned
            # unverified/failed/needs_verification, inject an explicit user-role
            # note so Gemma cannot silently move on as if everything succeeded.
            # H1: mapear cada result (por identidad) al error_type que el VERIFIER
            # ya clasificó en este mismo batch. Así la clasificación del verifier
            # (autoritativa: conoce el estado del SO que midió) gana sobre la
            # re-inferencia ciega por texto del result. Antes este bloque llamaba
            # classify_failure(r, "") con given=None -> ignoraba el error_type del
            # verifier por completo (el campo era 100% inerte fuera de su declaración).
            # events[-N:] y verifier_outcomes[-N:] son 1:1 (Phase 3 appendea uno de
            # cada por call, mismo orden que raw_tool_calls).
            _n_batch = len(raw_tool_calls)
            _result_etype = {
                id(ev.result): outcome.error_type
                for ev, outcome in zip(events[-_n_batch:],
                                       verifier_outcomes[-_n_batch:])
            }
            unverified_pairs = [
                ((raw_call.get("function") or {}).get("name", ""), ev.result)
                for raw_call, ev in zip(raw_tool_calls, events[-len(raw_tool_calls):])
                if _is_unverified_result(ev.result)
            ]
            unverified_in_batch = [name for name, _ in unverified_pairs]
            if unverified_in_batch:
                summary = ", ".join(unverified_in_batch[:6])
                if _error_recovery_enabled():
                    # B1 (competidores): recuperación por TIPO de error. Clasificamos
                    # el fallo y damos una directiva ESPECÍFICA (replan/amend/skip) en
                    # vez del nudge genérico, para que el loop se auto-corrija. Sólo
                    # cambia el TEXTO del hint (mismo mecanismo, mismo loop_detector
                    # + max_turns de guarda) -> bajo riesgo. Capa genérica, el LLM decide.
                    # H1: given = el error_type del verifier (si lo seteó) -> autoritativo.
                    _etypes = {
                        n: _classify_failure(r, "", given=_result_etype.get(id(r)))
                        for n, r in unverified_pairs
                    }
                    _vals = list(_etypes.values())
                    # H2: elegir la clase DOMINANTE por prioridad de recuperabilidad
                    # (precondition > param > transient > tool_not_found > unknown).
                    # Luego consultar el budget POR CLASE: si ya se gastó, el hint
                    # deja de pedir reintento y pasa a "escalá honestamente".
                    if ERR_MISSING_PRECONDITION in _vals:
                        _cls = ERR_MISSING_PRECONDITION
                    elif ERR_PARAM_MISMATCH in _vals:
                        _cls = ERR_PARAM_MISMATCH
                    elif ERR_TRANSIENT in _vals:
                        _cls = ERR_TRANSIENT
                    elif ERR_TOOL_NOT_FOUND in _vals:
                        _cls = ERR_TOOL_NOT_FOUND
                    else:
                        _cls = ERR_UNKNOWN
                    _budget = _retry_budget_for(_cls)
                    _spent = _retry_spent.get(_cls, 0)
                    _budget_left = _spent < _budget
                    if not _budget_left:
                        # Budget agotado (o clase irrecuperable: tool_not_found /
                        # unknown tienen budget 0 -> directo a escalar). NO pedir más
                        # reintentos: eso es el "466/513 desperdiciados". Honestidad.
                        if _cls == ERR_TOOL_NOT_FOUND:
                            _directive = ("Esa herramienta/acción NO existe: reintentarla da el "
                                          "mismo error. Elegí OTRA herramienta del subset, o decile "
                                          "honestamente al usuario que no tenés esa capacidad. NO "
                                          "repitas la misma llamada.")
                        else:
                            _directive = ("Ya se agotaron los reintentos para este tipo de fallo. "
                                          "NO reintentes más la misma acción: decile honestamente al "
                                          "usuario qué no se pudo y, si hace falta, pedile ayuda.")
                    elif _cls == ERR_MISSING_PRECONDITION:
                        _directive = ("El objetivo aún no existe (falta un paso previo): primero "
                                      "hacé el prerequisito (abrir/crear lo que falta) y RECIÉN "
                                      "ahí reintentá. No afirmes que ya está.")
                    elif _cls == ERR_PARAM_MISMATCH:
                        _directive = ("Faltó o erró un dato: reintentá la MISMA acción corrigiendo "
                                      "los argumentos, o pedile al usuario el dato que falta. No "
                                      "afirmes que ya está.")
                    elif _cls == ERR_TRANSIENT:
                        _directive = ("Falló por algo temporal: reintentá UNA vez; si vuelve a "
                                      "fallar, decile honestamente al usuario que no se pudo.")
                    else:
                        _directive = ("Reintentá con otra herramienta o argumentos distintos, o "
                                      "decile honestamente qué no se pudo verificar.")
                    if _budget_left:
                        _retry_spent[_cls] = _spent + 1
                    self.history.append({
                        "role": "user",
                        "content": f"[system note] La(s) acción(es) {summary} NO se verificaron. {_directive}",
                    })
                    self.trace.event(turn_id, "error_recovery_hint",
                                     tools=unverified_in_batch, types=_vals,
                                     err_class=_cls, budget_left=_budget_left,
                                     spent=_retry_spent.get(_cls, 0))
                else:
                    self.history.append({
                        "role": "user",
                        "content": (
                            "[system note] In the previous step, these tools returned "
                            f"unverified/failed results: {summary}. Do NOT claim those "
                            "actions are complete. Either run a verify(...), retry with "
                            "different args, or tell the user honestly what could not be "
                            "verified."
                        ),
                    })
                    self.trace.event(turn_id, "unverified_intermediate_warning", tools=unverified_in_batch)

            # CHAINING NUDGE (Problema B): un tool de BÚSQUEDA/LISTADO
            # (filesystem.search, local_search, ...) que devuelve ITEMS NO es el
            # final del turno — el usuario casi siempre quiere ALGO con el primer
            # resultado (abrir/reproducir/leer). Gemma E4B (4B) tiende a parar ahí
            # ("ya busqué, listo") sin encadenar el segundo paso. Bug sesión #847:
            # filesystem.search encontró el .docx pero NUNCA encadenó office.open.
            # Inyectamos un nudge que lo empuja a usar el resultado. Solo cuando:
            # la búsqueda fue EXITOSA y trajo items (si vino vacía, el honesty
            # guard de arriba ya maneja el "no encontré nada").
            chain_hint = self._chaining_nudge(raw_tool_calls, events)
            if chain_hint and not research_fallback_answer_only:
                self.history.append({"role": "user", "content": chain_hint})
                self.trace.event(turn_id, "chaining_nudge_injected", hint=chain_hint[:120])

            if research_fallback_answer_only:
                selected_tool_names = []
                selected_schemas = []
                mode = choose_mode(raw_text_early or "", "fast_info", self.config.max_tokens)
                self.history.append({
                    "role": "user",
                    "content": (
                        "[system note] You already have the search results for "
                        "this research follow-up. Answer now from the returned "
                        "tool evidence in the user's selected language. Do not "
                        "acknowledge the search; give the factual answer. Do not "
                        "call more tools."
                    ),
                })
                self.trace.event(turn_id, "research_fallback_answer_only")
                self._research_fallback_answer_pending = True
                research_fallback_answer_only = False

            # FAST PATH lectura de pantalla: vision.describe_screen ya hizo la
            # llamada visual y devolvio texto en result.description. Pedirle al
            # LLM otro pass solo para resumir esa descripcion agrega segundos y,
            # en modo no-vidente, puede disparar nudges extra. Cerramos el turno
            # directo solo si el ULTIMO evento es vision con descripcion.
            direct_screen_reply = self._screen_description_reply(events[-1:])
            if direct_screen_reply:
                mission_outcome = None
                try:
                    _tool_records_for_outcome = _build_tool_records(events, verifier_outcomes)
                    mission_outcome = _compute_mission_outcome(
                        mission_goal, _tool_records_for_outcome, direct_screen_reply,
                    )
                    self.trace.event(
                        turn_id, "mission_outcome",
                        status=mission_outcome.status.value,
                        summary=mission_outcome.summary,
                        confirmed=mission_outcome.confirmed_count,
                        failed=mission_outcome.failed_count,
                        unverified=mission_outcome.unverified_count,
                        expected_total=mission_outcome.expected_total,
                        expected_satisfied=mission_outcome.expected_satisfied,
                    )
                except Exception as _mo_exc:  # noqa: BLE001
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        "mission outcome direct screen failed: %s", _mo_exc)
                    try:
                        self.trace.event(turn_id, "mission_outcome_error",
                                         error=f"{type(_mo_exc).__name__}: {_mo_exc}")
                    except Exception:
                        pass
                mission = evaluate_mission(events, direct_screen_reply, plan)
                if isinstance(mission, dict) and mission_outcome is not None:
                    mission["mission_goal_status"] = mission_outcome.status.value
                    mission["mission_goal_summary"] = mission_outcome.summary
                    mission["mission_goal_progress"] = [
                        mission_outcome.expected_satisfied,
                        mission_outcome.expected_total,
                    ]
                self.history.append({"role": "assistant", "content": direct_screen_reply})
                used_tools = {e.name for e in events}
                self.trace.event(
                    turn_id, "screen_description_direct_final",
                    content_chars=len(direct_screen_reply),
                    saved_followup_llm=True,
                )
                self.trace.event(
                    turn_id, "router_stats",
                    subset_size=len(selected_tool_names),
                    used_count=len(used_tools),
                    unused_count=len(set(selected_tool_names) - used_tools),
                    used=sorted(used_tools),
                    unused=sorted(set(selected_tool_names) - used_tools),
                )
                self.trace.event(
                    turn_id, "final",
                    content=direct_screen_reply,
                    tool_events=len(events),
                    mission=mission,
                )
                self._record_experience_turn(
                    content=content,
                    assistant_content=direct_screen_reply,
                    events=events,
                    mission=mission,
                    turn_id=turn_id,
                )
                self._compact_completed_history()
                _progress(progress, "final", tools=len(events), mission=mission)
                self._last_turn_ts = time.time()
                self._remember_executed_tools(events)
                return AgentReply(
                    content=direct_screen_reply,
                    tool_events=events,
                    mission=mission,
                )

            # Loop detector check: si critical, abort el outer for y produci un
            # reply honesto. Si warning, inyecta el mensaje al historial para que
            # el LLM lo vea en el proximo client.chat() y corrija solo.
            stuck = loop_state.detect_stuck()
            if stuck is not None:
                self.trace.event(
                    turn_id, "loop_detector",
                    level=stuck.level, pattern=stuck.pattern, detail=stuck.detail,
                )
                _progress(progress, "loop_detector",
                          level=stuck.level, pattern=stuck.pattern)
                if stuck.level == "critical":
                    self.history.append({
                        "role": "user",
                        "content": stuck.message,
                    })
                    loop_aborted = True
                    break  # sale del outer `for _turn in range(max_agent_turns)`
                else:
                    # warning: nudge al LLM, sigue el loop normal
                    self.history.append({
                        "role": "user",
                        "content": stuck.message,
                    })

            # Replanning trigger: 2+ tool failures while we have an explicit
            # plan and have not replanned yet. Cheap: one extra LLM call.
            if (
                not replan_done
                and self._explicit_plan_text
                and len(failure_log) >= 2
            ):
                self.trace.event(turn_id, "replan_start", failures=len(failure_log))
                try:
                    from ..mission.explicit_plan import replan
                    # `raw_text` vivía en _decide_turn; al extraer _execute_turn
                    # (refactor R1, 25261147) quedó como variable libre acá — un
                    # NameError latente que solo dispara en el trigger de replan
                    # (2+ fallas de tool con plan explícito). En este scope el
                    # texto del usuario es `raw_text_early` (= decision.raw_text_early),
                    # que es justo el `user_text` que replan() espera. Misma
                    # clase que el bug `_os`.
                    revised = replan(
                        raw_text_early or "",
                        self._explicit_plan_text,
                        failure_log,
                        chat_fn=lambda msgs: self.client.chat(msgs, tools=None, enable_thinking=False, parallel_tool_calls=False, max_tokens=350, timeout_s=45.0),
                    )
                    if revised.get("ok") and revised.get("plan"):
                        self._explicit_plan_text = str(revised["plan"])
                        self._explicit_plan_steps = list(revised.get("steps") or [])
                        replan_done = True
                        self.trace.event(turn_id, "replan_ready",
                                         step_count=len(self._explicit_plan_steps),
                                         give_up=bool(revised.get("give_up")))
                    else:
                        self.trace.event(turn_id, "replan_failed", error=revised.get("error"))
                except Exception as exc:
                    self.trace.event(turn_id, "replan_error", error=str(exc))

        if loop_aborted:
            final = (
                "Detecte que estaba repitiendo la misma accion sin avanzar. "
                "Corte para no quemar tiempo. Decime que querias lograr o "
                "probemos otra estrategia."
            )
            reason = "loop_aborted"
        else:
            final = "No pude terminar la tarea dentro del limite de turnos."
            reason = "max_turns"
        mission = evaluate_mission(events, final, plan)
        self.history.append({"role": "assistant", "content": final})
        self.trace.event(turn_id, reason, content=final, tool_events=len(events), mission=mission)
        self._compact_completed_history()
        _progress(progress, "max_turns", tools=len(events), mission=mission)
        self._last_turn_ts = time.time()
        self._remember_executed_tools(events)
        # LECTURA DE PANTALLA (no-vidente): si la cadena se cortó (max_turns/loop)
        # pero vision YA describió la pantalla, devolver esa descripción en vez
        # del mensaje de corte — el usuario que no ve igual recibe la lectura.
        _scr = self._screen_description_reply(events)
        if _scr:
            final = _scr
        final = (final or "") + self._maybe_proactive_suffix(events)
        return AgentReply(content=final, tool_events=events, mission=mission)

    # Bodies moved to :mod:`.agent_dispatch`. The wrappers
    # below adapt the agent's positional progress callback to the
    # progress_emit(event, payload) callable the pure functions take.

    def _record_experience_turn(
        self,
        *,
        content: str | list[dict[str, Any]],
        assistant_content: str,
        events: list[ToolEvent],
        mission: dict[str, Any] | None,
        turn_id: str,
    ) -> None:
        """Persist a completed turn into semantic experience memory."""
        try:
            from ..routing import semantic_router as _semantic_router
            _semantic_ready = bool(_semantic_router.status().get("model_loaded"))
            if not _semantic_ready and not _experience_cold_load_enabled():
                self.trace.event(
                    turn_id,
                    "experience_record_skipped",
                    reason="semantic_encoder_cold",
                )
                return
            raw_text = _extract_user_text(content)
            used_tools = sorted({e.name for e in events})
            mission_status = (mission or {}).get("mission_status") if isinstance(mission, dict) else None
            outcome_code = _derive_outcome_code(mission_status, events)
            capability_label = None
            args_signature = _derive_args_signature(events)
            rec = self.experience.record(
                turn_id=turn_id,
                user_input=raw_text,
                tools_used=used_tools,
                outcome=assistant_content[:1000],
                mission_status=mission_status,
                summary=assistant_content[:400],
                embed_fn=_semantic_router.embed,
                outcome_code=outcome_code,
                capability_label=capability_label,
                args_signature=args_signature,
            )
            if rec.get("ok"):
                self.trace.event(turn_id, "experience_recorded", id=rec.get("id"))
        except Exception as exc:
            self.trace.event(turn_id, "experience_record_failed", error=str(exc))

    def _finalize_turn(
        self,
        content: str | list[dict[str, Any]],
        assistant_content: str,
        events: list[ToolEvent],
        msg: dict[str, Any],
        raw_text_early: str,
        turn_id: str,
        verifier_outcomes: list,
        mission_goal: Any,
        plan: dict[str, Any] | None,
        selected_tool_names: list[str],
        progress: ProgressCallback | None = None,
        mode: Any = None,
    ) -> "AgentReply | _FinalizeContinue":
        """Finalize phase of a turn.

        `mode` (AgentMode del turno) se usa para NO aplicar la reparación
        post-acción a turnos research/info (que ya respondieron con evidencia).
        Default None -> el guard `_is_research_mode` lo trata como no-research.

        Runs ONLY when the LLM finished without emitting a tool call
        (the natural success path). Applies post-processing:
        accessibility nudges, mission outcome, verifier footer,
        screen-description fallback, proactive suffix.

        Returns the terminal AgentReply, OR _FINALIZE_CONTINUE if
        the a11y nudge re-prompted (the caller must `continue` its
        outer for _turn loop).
        """
        # Imports que originalmente vivían dentro de
        # _execute_turn pero el finalize body los usa. Replicados acá para
        # mantener mecánica exacta sin tocar imports module-level.
        from ..safety_pkg.verify_core import summarize_verifiers
        from ..mission.mission_outcome import (
            build_tool_records as _build_tool_records,
            compute_mission_outcome as _compute_mission_outcome,
            mission_footer as _mission_footer,
        )
        if (
            getattr(self, "_research_fallback_answer_pending", False)
            and not getattr(self, "_research_fallback_answer_reprompted", False)
            and reply_validator.is_listo_on_no_tool_turn(assistant_content or "", [])
        ):
            self._research_fallback_answer_reprompted = True
            self.history.append({
                "role": "user",
                "content": (
                    "[system note] Your previous reply was only a post-tool "
                    "acknowledgement. The user asked an information question. "
                    "Answer the question now using the immediately preceding "
                    "web.search result. Do not say only 'Listo'/'Done'; do "
                    "not call tools."
                ),
            })
            self.trace.event(
                turn_id, "research_fallback_ack_reprompt",
                reply_preview=(assistant_content or "")[:80],
            )
            return _FINALIZE_CONTINUE
        # REDES DETERMINISTAS (fallback final). Las redes de
        # responder-mensaje / email / navegación son detectores de ALTA
        # precisión (verbo + 'a <destinatario>' + cuerpo; o URL/sitio
        # claros). Antes solo corrían dentro de forced_tool_retry_empty,
        # que se SALTEA cuando el abstain-head juzga el turno "no-tool" y
        # deja el subset sin la tool de dominio (medido: "respondele a mama
        # que ya voy" -> subset=[session], el 4B se niega). Acá las
        # disparamos AUNQUE el abstain head haya abstenido — desacopladas
        # del router — pero SOLO si ninguna tool corrió aún este turno
        # (len(events)==0) y el forced-retry no las probó ya. Cada red es
        # conservadora (None si no hay match claro) -> no roba turnos de
        # charla. Fallback seguro: error -> seguimos al flujo normal.
        if (_GUARDS_ON and len(events) == 0
                and not getattr(self, "_det_nets_tried", False)):
            self._det_nets_tried = True
            try:
                _dn_ev = (self._deterministic_reply(raw_text_early)
                          or self._deterministic_email(raw_text_early)
                          or self._deterministic_navigate(raw_text_early))
            except Exception as _dnexc:
                _dn_ev = None
                try:
                    self.trace.event(turn_id, "deterministic_net_error",
                                     error=f"{type(_dnexc).__name__}: {_dnexc}")
                except Exception:
                    pass
            if _dn_ev is not None and (_dn_ev.result or {}).get("ok"):
                events.append(_dn_ev)
                _nm = _dn_ev.name
                self.trace.event(turn_id, "deterministic_net_fallback",
                                 tool=_nm)
                _res = _dn_ev.result or {}
                if _nm == "whatsapp":
                    _rc = _res.get("reply_contact") or ""
                    assistant_content = (
                        f"Abrí el chat con {_rc} y dejé el mensaje listo. "
                        "Revisalo y decime si lo envío.")
                elif _nm == "email":
                    _to = _res.get("email_to") or ""
                    assistant_content = (
                        f"Abrí el borrador de correo para {_to}. "
                        "Revisalo y decime si lo envío.")
                else:  # browser
                    _u = _res.get("resolved_url") or _res.get("url") or ""
                    assistant_content = f"Listo, abrí {_u}."
                raw_msg = {}
                # con la red disparada, saltamos los guards de "prometió
                # sin acción" (ya hay un evento real) y finalizamos.
                msg["content"] = assistant_content
        # ACCESIBILIDAD (B3/B4) — CONTINUAR EN EL MISMO TURNO. En
        # movilidad/no_vidente el agente debe HACER TODO por el usuario:
        # si está por terminar con una respuesta que DELEGA la tarea
        # ("revisá los resultados", "elegí cuál", "mirá la pantalla y
        # decidí"), NO finalizamos — inyectamos un nudge y re-prompteamos
        # al LLM para que ejecute el SIGUIENTE paso él mismo, dentro de
        # este turno. Acotado por _A11Y_MAX_CONTINUES para "avanzar lo más
        # posible y después parar honesto" (el 4B se traba en cadenas
        # largas; no queremos un loop infinito). Aplica a CUALQUIER tarea,
        # no solo compras. Fallback seguro: cualquier error -> finaliza.
        _cont_delegates = None
        try:
            from .. import accessibility as _a11y_cont
            from ..safety_pkg.reply_validator import reply_delegates_task as _rdt_cont
            _cont_mode = _a11y_cont.get_active_mode()
            _cont_active = _cont_mode.hands_free_only or _cont_mode.narrate_all_actions
            if _cont_active:
                _cont_delegates = _rdt_cont(assistant_content or "")
        except Exception:
            _cont_active = False
            _cont_delegates = False
        # GUARD (bug medido): el nudge "ejecutá vos el siguiente
        # paso" SOLO tiene sentido en un turno de ACCIÓN (cuando el comando pidió
        # HACER algo). En una pregunta META/charla ("¿qué podés hacer?",
        # "¿quién eres?") el router ABSTUVO (subset sin tools de dominio) y
        # no corrió ninguna acción: la respuesta DESCRIBE capacidades, no
        # delega una tarea. Sin este gate, en movilidad/no_vidente el 4B
        # tomaba la descripción ("...controlar tu sistema, gestionar apps...")
        # como tarea-a-continuar y el nudge lo empujaba a sacar un screenshot
        # para responder "¿qué podés hacer?" (absurdo, 5/5 medido). Actionable
        # = se ofreció ≥1 tool de dominio este turno O se ejecutó una acción
        # de dominio. Estructural (estado del router/ejecución), no contenido.
        _cont_actionable = False
        _only_web_search = False
        try:
            _dom_offered = bool(_domain_subset(list(selected_tool_names)))
            _dom_events = [e for e in events
                           if e.name not in {"session", "safety", "state", "verify"}]
            _dom_ran = bool(_dom_events)
            _cont_actionable = _dom_offered or _dom_ran
            # Bug (movilidad/no_vidente): si lo ÚNICO que corrió fue una
            # BÚSQUEDA WEB informacional, NO hay tarea física pendiente — responder/
            # sintetizar YA completó el turno. Sin este guard, el continue-nudge
            # empujaba a un "siguiente paso" físico inexistente y el 4B colapsaba a
            # reply VACÍO ("explicame qué es Python" -> web -> ""). Estructural.
            _only_web_search = _dom_ran and all(
                e.name in {"web", "browser", "browser_real"}
                and isinstance(getattr(e, "result", None), dict)
                and "search" in str((e.result or {}).get("action") or "").casefold()
                for e in _dom_events
            )
        except Exception:
            _cont_actionable = True  # ante la duda, no bloquear el nudge
            _only_web_search = False
        # En fast_info, si este turno YA corrió una lectura VISUAL exitosa
        # (gui screenshot / vision), el nudge es redundante por definición: su
        # texto pide "capturá la pantalla con vision si necesitás leer" y eso
        # acaba de pasar — la descripción ES la respuesta. MEDIDO 2026-06-12:
        # "Que hay en la pantalla?" → screenshot real + descripción fundada
        # ("Veo la ventana de Discord…") y el nudge (falso-positivo de
        # delegación sobre la descripción) re-prompteaba 2-3 veces hasta
        # degradar el reply a "Listo.". Un turno de ACCIÓN que delega sin
        # lectura visual (p.ej. window.list + "revisá y elegí") SÍ nudgea.
        _cont_info_question = (
            str(getattr(mode, "name", "") or "") == "fast_info"
            and any(
                getattr(e, "name", "") in {"gui", "vision"}
                and isinstance(getattr(e, "result", None), dict)
                and (e.result or {}).get("ok") is True
                for e in events)
        )
        if (_cont_active
                and _cont_actionable
                and not _only_web_search
                and not _cont_info_question
                and self._a11y_continue_count < _A11Y_MAX_CONTINUES
                and _cont_delegates):
            self._a11y_continue_count += 1
            self.trace.event(
                turn_id, "a11y_continue_nudge",
                attempt=self._a11y_continue_count,
                reply_preview=(assistant_content or "")[:120],
            )
            self.history.append({"role": "assistant",
                                 "content": assistant_content or ""})
            self.history.append({
                "role": "user",
                "content": (
                    "[system note] No delegues la tarea en mí: no puedo "
                    "revisar la pantalla, elegir ni hacer clic. EJECUTÁ "
                    "vos el siguiente paso ahora con una tool-call "
                    "(capturá la pantalla con vision si necesitás leer "
                    "los resultados, abrí el resultado correcto vos "
                    "mismo, y seguí). Si de verdad te trabás, decímelo "
                    "con honestidad — pero primero intentá el próximo "
                    "paso."
                ),
            })
            return _FINALIZE_CONTINUE
        chain_question = self._filesystem_search_clarification(
            events, raw_text_early,
        )
        if chain_question:
            assistant_content = chain_question["content"]
            msg["content"] = assistant_content
            try:
                if hasattr(self.state, "set_pending_intent"):
                    self.state.set_pending_intent(
                        tool=str(chain_question.get("target_tool") or "office"),
                        args=dict(chain_question.get("args") or {}),
                        asks_for="file_selection",
                        current_turn=self._turn_counter,
                        ttl_turns=2,
                    )
                self.trace.event(
                    turn_id,
                    "filesystem_search_clarification",
                    candidates=len(chain_question.get("paths") or []),
                    target_tool=str(chain_question.get("target_tool") or "office"),
                )
            except Exception as _exc:  # noqa: BLE001
                try:
                    self.trace.event(
                        turn_id,
                        "silent_fallback",
                        component="filesystem_search_clarification",
                        error=f"{type(_exc).__name__}: {_exc}",
                    )
                except Exception:
                    pass
        # Rama Experimentando: SIN repairs ni forzado de idioma. sanitize_text es
        # DECODIFICACIÓN de salida (strippea el canal <think>/<|tool_call>), no un guard.
        assistant_content = sanitize_text(assistant_content)
        # HONESTIDAD (ÚNICO guard de comportamiento conservado — medido load-bearing):
        # el E2B confabula éxito ~12% de las veces ("Listo, hice X" SIN ninguna tool
        # verificada — el experimento descartó FT/E4B/formato para ese piso). Este
        # guard ESTRUCTURAL (detect_action_claim_without_evidence: mide la FORMA, claim
        # sin evidencia — NO listas de keywords) reescribe la mentira a una forma
        # honesta. No es sobreingeniería: compensa un límite intrínseco del modelo chico.
        # Pase 1: cero-eventos / verificación fallida — caza "Listo, abrí Gmail" con
        # exec=[] (la confabulación de navegación/open que el grounded-claim no ve, porque
        # no hay tool que inspeccionar). Estructural (reply_claims_action = forma verbal).
        if _GUARDS_ON:
            try:
                from .agent_guards import guard_unverified_final as _guf
                assistant_content = _guf(assistant_content, events)
            except Exception:
                pass
            # Pase 2: claim de acción sin evidencia sobre una tool que SÍ corrió.
            assistant_content = self._guard_grounded_action_claim(assistant_content, events, turn_id)
        # Defensa: si el LLM emitio en el reply mismo un footer estilo
        # "[N verificada(s)]" o "[misión: ...]" (porque vio uno en el
        # historial), lo strippeamos antes de pegar el nuestro. Sino,
        # el reply muestra footers duplicados.
        assistant_content = _strip_trailing_footers(assistant_content)
        # IMPORTANTE: guardamos en el history la version SIN footers.
        # Los footers son metadata para el usuario, no contenido. Si
        # los pegaramos al history, el LLM los veria como contenido
        # legitimo del asistente y los reproduciria proximo turn,
        # bloating context + duplicando texto.
        content_for_history = assistant_content
        # TIER 1 #2: footer estructural honest del verifier per-tool.
        # Solo aparece si hay failed o unverifiable; silencioso si todo OK.
        verifier_footer = summarize_verifiers(verifier_outcomes)
        if verifier_footer:
            assistant_content = assistant_content + verifier_footer
            self.trace.event(
                turn_id, "verifier_footer",
                confirmed=sum(1 for o in verifier_outcomes if o.confirmed is True),
                failed=sum(1 for o in verifier_outcomes if o.confirmed is False),
                unverifiable=sum(1 for o in verifier_outcomes if o.confirmed is None),
            )
        # TIER 2 #5: MissionOutcome — status semantico final del turn.
        # Combina mission_goal (objective fulfilled?) con verifier counts
        # (per-tool measured effect) y emite footer SOLO si aporta info
        # (PARTIAL/FAILED/INTENT_NOT_FULFILLED/TOOL_OK_VERIFIER_INCONCLUSIVE).
        # The mission-outcome footer is post-reply ENRICHMENT (cosmetic
        # metadata). A bug in build/compute/footer must NEVER destroy a
        # reply the LLM already produced — same invariant as the verifier
        # and tracing fixes. On failure keep assistant_content as-is and
        # leave mission_outcome=None (guarded downstream).
        mission_outcome = None
        try:
            _tool_records_for_outcome = _build_tool_records(events, verifier_outcomes)
            mission_outcome = _compute_mission_outcome(
                mission_goal, _tool_records_for_outcome, content_for_history,
            )
            _mission_extra_footer = _mission_footer(mission_outcome)
            if _mission_extra_footer:
                assistant_content = assistant_content + _mission_extra_footer
            self.trace.event(
                turn_id, "mission_outcome",
                status=mission_outcome.status.value,
                summary=mission_outcome.summary,
                confirmed=mission_outcome.confirmed_count,
                failed=mission_outcome.failed_count,
                unverified=mission_outcome.unverified_count,
                expected_total=mission_outcome.expected_total,
                expected_satisfied=mission_outcome.expected_satisfied,
            )
        except Exception as _mo_exc:  # noqa: BLE001
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "mission outcome footer failed: %s", _mo_exc)
            try:
                self.trace.event(turn_id, "mission_outcome_error",
                                 error=f"{type(_mo_exc).__name__}: {_mo_exc}")
            except Exception:
                pass
        mission = evaluate_mission(events, assistant_content, plan)
        # Enriquecer el mission dict legacy con el outcome estructural
        # (no rompe consumidores existentes — agrega claves nuevas).
        if isinstance(mission, dict) and mission_outcome is not None:
            mission["mission_goal_status"] = mission_outcome.status.value
            mission["mission_goal_summary"] = mission_outcome.summary
            mission["mission_goal_progress"] = [
                mission_outcome.expected_satisfied,
                mission_outcome.expected_total,
            ]
        # NET de empty-reply (replay de logs): si tras TODO el rescue/
        # retry/finalización el reply queda VACÍO, NUNCA dejar al user en silencio
        # (medido: el 4B a veces devuelve content vacío, p.ej. gui-calc "escribí
        # 11x11"). Fallback context-aware: con tools ejecutadas = confirmación; sin
        # tools = pedir reformular. Es una GUARDA estructural de último recurso (la
        # forma es "reply vacío", no una respuesta enlatada a una query) + queda el
        # event para diagnóstico de la causa de fondo.
        if _GUARDS_ON and not (assistant_content or "").strip():
            assistant_content = ("Listo." if events
                                 else "Perdón, no pude generar una respuesta. ¿La reformulás?")
            content_for_history = assistant_content
            try:
                self.trace.event(turn_id, "empty_reply_fallback", had_tools=bool(events))
            except Exception:
                pass
        # History recibe la version SIN footers (ver comentario arriba).
        self.history.append({"role": "assistant", "content": content_for_history})
        # Subset summary: which sent tools were actually used vs idle.
        used_tools = {e.name for e in events}
        router_stats = {
            "subset_size": len(selected_tool_names),
            "used_count": len(used_tools),
            "unused_count": len(set(selected_tool_names) - used_tools),
            "used": sorted(used_tools),
            "unused": sorted(set(selected_tool_names) - used_tools),
        }
        self.trace.event(turn_id, "router_stats", **router_stats)
        self.trace.event(turn_id, "final", content=assistant_content, tool_events=len(events), mission=mission)
        # Persist this turn into semantic experience memory (hint-only,
        # never blocks). Best-effort: failure is logged and swallowed.
        # Bug 2: also persist provenance fields so future RAG hits
        # can be formatted as policy hints (not reply templates).
        self._record_experience_turn(
            content=content,
            assistant_content=assistant_content,
            events=events,
            mission=mission,
            turn_id=turn_id,
        )
        # Fact extraction: opt-in via env. Cooldown so we do not call
        # the LLM every turn. Skips short / trivial turns.
        # LATENCIA: este es un 2º LLM call (~200 tok) que NO aporta al
        # reply del usuario — antes corría SÍNCRONO acá, sumando su decode
        # al tiempo que el usuario espera. Lo movemos a un daemon thread:
        # el reply se devuelve YA, la extracción de facts ocurre en
        # background. Marcamos el cooldown ANTES de spawnnear (no dispara
        # dos veces) y la persistencia (memory.auto_save) tiene su propio
        # lock. Best-effort: un fallo en el thread se traza, no afecta el
        # turno (que ya retornó).
        if _fact_extraction_enabled():
            cooldown = _fact_extraction_cooldown_turns()
            if (self._turn_counter - self._fact_extract_last_run_turn) >= cooldown:
                raw_text_now = _extract_user_text(content)
                if raw_text_now and len(raw_text_now.split()) >= 5:
                    self._fact_extract_last_run_turn = self._turn_counter
                    _ft_user, _ft_reply, _ft_turn = (
                        raw_text_now, assistant_content, turn_id)

                    def _bg_extract_facts() -> None:
                        try:
                            facts = self._extract_facts(_ft_user, _ft_reply)
                            if facts:
                                save_result = self.memory.auto_save(facts)
                                self.trace.event(_ft_turn, "facts_extracted",
                                                 count=len(facts),
                                                 added=save_result.get("added"),
                                                 total_auto=save_result.get("total_auto"))
                            else:
                                self.trace.event(_ft_turn, "facts_extraction_empty")
                        except Exception as exc:
                            self.trace.event(_ft_turn, "facts_extraction_failed",
                                             error=str(exc))

                    import threading as _threading
                    _threading.Thread(target=_bg_extract_facts,
                                      name="gemma4-fact-extract",
                                      daemon=True).start()

        # Hotfix I: pending_intent rescue when
        # the LLM asks a clarifying question on its own
        # (Bug D8 part 2 — no tool returned needs_user, the
        # LLM just decided to ask). Only fires when nothing
        # better is already stashed.
        try:
            _pending_target = _should_set_pending_intent_from_reply(
                reply_text=assistant_content or "",
                tool_calls_this_turn=list(events),
                selected_tool_names=list(selected_tool_names),
            )
            if _pending_target and hasattr(self.state, "get_pending_intent") and not self.state.get_pending_intent(self._turn_counter):
                _target_tool, _asks_for = _pending_target
                self.state.set_pending_intent(
                    tool=_target_tool,
                    args={},
                    asks_for=_asks_for,
                    current_turn=self._turn_counter,
                    ttl_turns=2,
                )
                self.trace.event(
                    turn_id, "pending_intent_from_reply_shape",
                    target_tool=_target_tool,
                    reason="reply_ended_with_question_no_tool",
                )
        except Exception as _exc:  # noqa: BLE001
            try:
                self.trace.event(
                    turn_id, "silent_fallback",
                    component="pending_intent_from_reply_shape",
                    error=f"{type(_exc).__name__}: {_exc}",
                )
            except Exception:
                pass

        # Hotfix I: telemetry for the final-
        # stage Bug D1 symptom — domain tool in the subset
        # but the LLM didn't call anything. Pure
        # observability; no behavior change. Operators grep
        # for drift between subset selection and LLM use.
        try:
            _domain = _domain_subset(list(selected_tool_names))
            if _domain and len(events) == 0:
                self.trace.event(
                    turn_id, "tool_call_skipped_when_expected",
                    domain_subset=_domain,
                    reply_preview=(assistant_content or "")[:200],
                )
        except Exception as _exc:  # noqa: BLE001
            try:
                self.trace.event(
                    turn_id, "silent_fallback",
                    component="tool_call_skipped_telemetry",
                    error=f"{type(_exc).__name__}: {_exc}",
                )
            except Exception:
                pass


        self._compact_completed_history()
        _progress(progress, "final", tools=len(events), mission=mission)
        self._last_turn_ts = time.time()
        self._remember_executed_tools(events)
        # LECTURA DE PANTALLA (no-vidente): si vision produjo una
        # descripción, ÚSALA como reply (el 4B no la relata fiable).
        _scr = self._screen_description_reply(events)
        if _scr:
            assistant_content = _scr
        # La oferta proactiva SOLO en un breakpoint genuino: si el user acaba de
        # ejecutar una acción (events>0) está EN TAREA — colgar "por cierto, querés
        # que automatice X?" es intrusivo (auditoría 2026-06-07: "apenas abro la app
        # actúa"). Ofrecer solo en turnos conversacionales (sin tool ejecutado).
        assistant_content = (assistant_content or "") + self._maybe_proactive_suffix(events)
        # Rama Experimentando: SIN repair de idioma post-tool. El reply del LLM
        # queda en el idioma que el modelo eligió nativamente.
        # If we streamed an INFO pass but the turn then ran a tool (the model
        # emitted a web-call as text that the RESCUE executed -> a post-prose
        # tool+summary), the streamed knowledge prose was superseded by a verified
        # answer. Demote to NOT-streamed so the runner voices the VERIFIED final
        # (truthful, no verification bypass — the streamed prose was honest but is
        # no longer "the answer"). Pure-prose info turns (events==0) stay streamed.
        if getattr(self, "_tts_info_stream", False) and len(events) > 0:
            self._tts_streamed = False
            self._tts_streamed_text = ""
            self.trace.event(turn_id, "tts_info_stream_superseded", tools=len(events))
        # STREAMING TTS: if the prose was already voiced sentence-by-sentence
        # during generation, speak only the post-guard tail. For a clean success
        # this is empty. (Rama Experimentando: sin regen de idioma post-tool ni
        # guards de valor/hora — el reply nativo del LLM se entrega tal cual.)
        if getattr(self, "_tts_streamed", False):
            self._feed_tts_tail(assistant_content, turn_id)
        return AgentReply(content=assistant_content, tool_events=events, mission=mission,
                          tts_streamed=getattr(self, "_tts_streamed", False))

    def run_content(self, content: str | list[dict[str, Any]], progress: ProgressCallback | None = None,
                    *, tts_sink: "Callable[[str], int | None] | None" = None) -> AgentReply:
        _turn_perf_t0 = time.perf_counter()
        self._turn_perf_t0 = _turn_perf_t0
        # Per-turn TTS streaming sink (GEMMA4_STREAM_TTS, default off). _execute_turn
        # streams the summary-pass prose into this sink as it generates; _finalize_turn
        # feeds the post-guard tail. None in text/GUI mode -> no streaming (the
        # unchanged blocking path). Reset every turn so a stale sink never leaks.
        self._active_tts_sink = tts_sink
        self._tts_streamed = False
        self._tts_streamed_text = ""
        self._tts_info_stream = False  # did we stream an INFO (no-tool) pass this turn?
        # GROUNDING: plumbear el texto del turno al ToolRegistry ANTES de cualquier
        # despacho de tool (incl. short-circuits de _decide_turn). Las tools que
        # validan PROCEDENCIA (whatsapp: ¿el user DICTÓ este número o el 4B lo
        # alucinó?) lo leen de ahí. Acá es el único punto que corre SIEMPRE, antes
        # de los early-return. Best-effort.
        try:
            self.tools._current_user_text = (
                _extract_user_text(content) or "").strip().lower()
        except Exception:
            pass
        # La fase decide vivía inline acá (~782 LOC).
        # Extraída a _decide_turn. early_reply propaga los 4 caminos
        # cortos (jarvis-pending, multi-intent re-dispatch, reply-shortcut,
        # explicit-plan-only). Los 8 campos restantes son las locales que
        # cruzan la frontera decide → execute/finalize (mapeo AST verificó
        # que no hay más).
        _decision = self._decide_turn(content, progress)
        if _decision.early_reply is not None:
            self._emit_decide_timing(_decision, _turn_perf_t0, early=True)
            return self._ensure_nonempty_reply(_decision.early_reply)
        self._emit_decide_timing(_decision, _turn_perf_t0, early=False)
        # Confirm filler (modo voz): preámbulo hablado INMEDIATO mientras
        # _execute_turn corre el LLM (p50 2.2s de silencio en turnos de acción).
        # El reply REAL sale después; el filler nunca lo reemplaza.
        self._voice_action_filler(content, _decision)
        # La fase execute vivía inline acá (LLM loop
        # iterativo + tool dispatch + post-procesamiento). Extraída a
        # _execute_turn que devuelve el AgentReply terminal del turno.
        _reply = self._ensure_nonempty_reply(self._execute_turn(content, _decision, progress))
        # PREFIX-REWARM: reponer el prefijo grande en el KV del slot DESPUÉS de
        # devolver el reply (thread daemon; el TTS/UI no espera). Ver
        # _prefix_rewarm_async para la causa raíz medida.
        self._prefix_rewarm_async()
        return _reply

    def _emit_decide_timing(self, decision: "TurnDecision", t0: float,
                            *, early: bool) -> None:
        """Traza el wall-time de la fase decide (instrumentación de latencia,
        2026-06-09). Best-effort; no afecta la lógica del turno. Vive fuera de
        run_content para que el orquestador quede thin (ratchet R1)."""
        try:
            if early:
                self.trace.event(
                    decision.turn_id or "turn", "turn_timing", phase="decide_early",
                    wall_ms=round((time.perf_counter() - t0) * 1000.0, 3))
                return
            self.trace.event(
                decision.turn_id, "turn_timing", phase="decide",
                wall_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                mode=getattr(decision.mode, "name", None),
                tools=list(decision.selected_tool_names or []),
                schema_count=len(decision.selected_schemas or []),
                semantic_fallback=bool(decision.semantic_fallback),
            )
        except Exception:
            pass

    def _prefix_rewarm_async(self) -> None:
        """Re-calienta el prefix-cache del slot del server en el IDLE post-turno.

        CAUSA RAÍZ (medida en vivo, scripts/_diag/_probe_cache_divergence.py
        2026-06-12): el server corre con --parallel 1 (un solo slot de KV). Los
        pases utilitarios de fin de turno (_llm_action_reply, repairs de idioma,
        knowledge regen) usan un system propio de ~100 tokens — correcto para su
        función (contexto limpio anti-arrastre), pero REEMPLAZAN el KV del slot.
        El primer LLM-call del turno siguiente matchea solo ~4 tokens (el render
        diverge en el system) y re-prefilea ~6K tokens: ~1.1s extra de TTFT en
        el 77% de los turnos de prod (835 turnos auditados en traces.jsonl).

        FIX: tras devolver el reply (el usuario está escuchando el TTS), un
        thread daemon manda UNA request de prefill (max_tokens=1) con el system
        de ESTE turno. El slot queda cargado con el prefijo grande; el próximo
        turno diverge recién en la cola variable del system (~90%, layout V3) →
        prefill ~0.4s en vez de ~1.1s. El trabajo no desaparece: se corre en
        idle, fuera del camino crítico. No toca NINGÚN prompt que genere texto
        visible (cero riesgo de calidad).

        Guardas:
        - enable_thinking del MODO del turno (el render inyecta <|think|> en el
          token ~4; un flip ahí invalida todo el prefijo — medido).
        - stale-check: si ya arrancó otro turno cuando el thread despierta, se
          aborta (no compite con una request real; peor caso si pierde la
          carrera: la request real espera ~0.7s en cola, menos de lo que ahorra).
        - solo perfiles GPU (ngl>0): en CPU el prefill idle competiría con el
          TTS/STT que también corren en CPU.
        Gate: GEMMA4_PREFIX_REWARM=0 lo desactiva.
        """
        import os as _os_rw
        if _os_rw.environ.get("GEMMA4_PREFIX_REWARM", "1").strip().lower() \
                in {"0", "false", "no", "off"}:
            return
        sys_content = getattr(self, "_rewarm_system", "") or ""
        if not sys_content:
            return
        try:
            from ..infra.profiles import get_active_profile
            if int(get_active_profile().n_gpu_layers) <= 0:
                return
        except Exception:
            pass
        if getattr(self, "_rewarm_inflight", False):
            return
        self._rewarm_inflight = True
        thinking = bool(getattr(self, "_rewarm_thinking", True))
        turn_marker = getattr(self, "_turn_perf_t0", None)
        t_sched = time.perf_counter()

        def _go() -> None:
            try:
                # Stale-check: si run_content volvió a arrancar, abortar.
                if getattr(self, "_turn_perf_t0", None) is not turn_marker:
                    return
                _model = self._router_model_for([{"role": "user", "content": "."}])
                resp = self.client.chat(
                    [{"role": "system", "content": sys_content},
                     {"role": "user", "content": "."}],
                    tools=None, enable_thinking=thinking,
                    parallel_tool_calls=False, max_tokens=1,
                    thinking_budget=0, timeout_s=20.0, model=_model,
                )
                timings = (resp or {}).get("timings") or {}
                self.trace.event(
                    "agent", "prefix_rewarm",
                    thinking=thinking,
                    cache_n=timings.get("cache_n"),
                    prompt_n=timings.get("prompt_n"),
                    wall_ms=round((time.perf_counter() - t_sched) * 1000.0, 1),
                )
            except Exception:
                pass  # best-effort puro: nunca afecta el turno
            finally:
                self._rewarm_inflight = False

        try:
            import threading as _threading
            _threading.Thread(target=_go, daemon=True, name="prefix-rewarm").start()
        except Exception:
            self._rewarm_inflight = False

    def _voice_action_filler(self, content: str | list[dict[str, Any]],
                             decision: "TurnDecision") -> None:
        """Confirm filler (2026-06-10): voca un preámbulo corto con personalidad
        apenas la fase decide eligió tools de acción, mientras _execute_turn corre
        el LLM. Enmascara el silencio percibido (~2-4s medidos) sin tocar la
        latencia computacional. HONESTIDAD: el filler nunca promete nada que el
        resultado pueda contradecir (intent-aware solo con target claro + tool
        openable; ante duda, genérico — ver action_filler.py). El reply REAL se
        voca después por el camino normal; esto es un preámbulo, no un reemplazo.

        Gates (MEDIDOS en vivo, scripts/_validate_action_filler.py 2026-06-10):
        - sink no-None (texto/CLI pasan None; en el runner feed_tts no-opea sin
          TTS cargado).
        - modo *_action: en turnos info/chat el router puede OFRECER tools pero
          el 4B charla (medido: "qué linda mañana" -> reply 1.8s sin tool); el
          filler ahí es ruido. El modo de ACCIÓN es la señal estructural de que
          viene un tool-call lento. Info largo ya lo cubre el streaming TTS.
        - tools de DOMINIO elegidas: session/safety son meta-tools que acompañan
          a TODO turno (medido: charla "qué linda mañana" -> ['session',
          'safety'] en modo fast_action; acción real -> dominio + helpers). Un
          set solo-meta = charla, sin filler.
        - idioma con banco (es/en — en otros idiomas mejor silencio que vocar
          español).
        - intent-aware OPT-IN (GEMMA4_FILLER_INTENT=1, default OFF): medido que
          los "abrí X" fáciles salen por el app-open net en decide (~1s, early,
          sin filler) — al LLM llegan los que el net NO resolvió, así que el
          "Abriendo X" dispara sesgado hacia fallos (live: "Abriendo
          jitomatador." -> "No llegué a ejecutar ninguna acción" = contradice).
          Hasta plumbear el outcome del net, genérico siempre (nunca miente).
        Rotación por contador de instancia, sin random (rompe resume).
        Best-effort: un fallo acá jamás afecta el turno."""
        sink = getattr(self, "_active_tts_sink", None)
        tool_names = list(decision.selected_tool_names or [])
        mode_name = getattr(decision.mode, "name", "") or ""
        if (sink is None or "action" not in mode_name
                or not any(t not in ("session", "safety") for t in tool_names)):
            return
        try:
            from .action_filler import pick_filler, intent_target_for_filler
            utext = decision.raw_text_early or _extract_user_text(content) or ""
            lang = _reply_lang(utext)
            if lang not in ("es", "en"):
                return
            target = tool = None
            import os as _os_fil
            if (_os_fil.environ.get("GEMMA4_FILLER_INTENT", "0").strip().lower()
                    in {"1", "true", "yes", "on"}):
                target, tool = intent_target_for_filler(utext, tool_names)
            rotate = int(getattr(self, "_filler_rotate", 0))
            self._filler_rotate = rotate + 1
            text = pick_filler(lang=lang, rotate=rotate,
                               intent_target=target, intent_tool=tool)
            if not text:
                return
            sink(text + " ")
            self.trace.event(decision.turn_id or "turn", "action_filler",
                             text=text, lang=lang, intent_aware=bool(target),
                             mode=mode_name, tools=tool_names)
        except Exception:  # noqa: BLE001
            pass

    def _ensure_nonempty_reply(self, reply: "AgentReply | None") -> "AgentReply | None":
        """Net UNIVERSAL de empty-reply: el user NUNCA recibe
        silencio. Si el content del reply quedó vacío (error del LLM, degeneración
        del 4B, path no previsto), un fallback HONESTO context-aware. El runner
        TTS-ea reply.content cuando no hubo streaming → sin divergencia audio/display.
        Guarda estructural de último recurso (mide la FORMA 'reply vacío', no es una
        respuesta enlatada a una query); el event queda para diagnóstico."""
        if reply is None or (getattr(reply, "content", "") or "").strip():
            return reply
        if getattr(reply, "error", None):
            reply.content = "Tuve un problema técnico procesando eso. ¿Lo intentás de nuevo?"
        elif getattr(reply, "tool_events", None):
            reply.content = "Listo."
        else:
            reply.content = "Perdón, no pude generar una respuesta. ¿La reformulás?"
        try:
            self.trace.event("turn", "empty_reply_fallback_universal",
                             had_tools=bool(getattr(reply, "tool_events", None)),
                             had_error=bool(getattr(reply, "error", None)))
        except Exception:
            pass
        return reply

    def _execute_calls_sequential(
        self,
        prepared: list[dict[str, Any]],
        progress: ProgressCallback | None,
        base_count: int,
        *,
        turn_id: str = "",
    ) -> None:
        from .agent_dispatch import execute_calls_sequential
        execute_calls_sequential(
            prepared,
            tools_registry=self.tools,
            trace=getattr(self, "trace", None),
            run_with_timeout=_run_with_timeout,
            progress_emit=lambda event, payload: _progress(progress, event, **payload),
            base_count=base_count,
            turn_id=turn_id,
        )

    def _execute_calls_parallel(
        self,
        prepared: list[dict[str, Any]],
        progress: ProgressCallback | None,
        base_count: int,
        *,
        turn_id: str = "",
    ) -> None:
        from .agent_dispatch import execute_calls_parallel
        execute_calls_parallel(
            prepared,
            tools_registry=self.tools,
            trace=getattr(self, "trace", None),
            progress_emit=lambda event, payload: _progress(progress, event, **payload),
            base_count=base_count,
            turn_id=turn_id,
        )

    def _router_model_for(self, messages: list[dict[str, Any]]) -> str | None:
        """Pick the router preset for THIS call based on the actual messages.

        Vision preset when the outgoing messages carry an image (mode-driven
        OR a mid-turn tool injection like a screenshot), else the text preset.
        None when not in router mode (caller falls back to the configured
        model). Server-driven so it works in any process."""
        has_image = _messages_have_image(messages)
        try:
            from ..infra.llama_server import resolve_turn_model
            m = resolve_turn_model(has_image=has_image)
            if m is not None:
                return m
        except Exception:
            pass
        # Fall back to whatever was resolved at turn start.
        return getattr(self, "_router_model", None)

    # Tools whose DELIVERABLE is the picture itself — a screenshot/visual read
    # the user asked for. Their image must reach the LLM. Everything else that
    # happens to carry an `image_path` (media/browser play, app open, etc.)
    # attached it as VERIFICATION evidence for the verifier, not as LLM input.
    _VISUAL_DELIVERABLE_TOOLS = frozenset({"gui", "vision", "uia", "verify"})
    # Result.action values that mean "I captured an image on purpose".
    _VISUAL_ACTIONS = ("screenshot", "capture", "ocr", "read_screen", "describe")

    def _run_multi_intent(self, clauses: list[str], progress=None) -> "AgentReply":
        """Ejecuta cada cláusula de un comando multi-intent como su propio turno
        (inv 7). Serializado: las cláusulas dependientes ('...y abrilo') usan el
        inherit-tools del turno previo. Combina las respuestas en un solo reply.
        _splitting evita que cada sub-turno vuelva a partir."""
        self._splitting = True
        replies: list[str] = []
        all_events: list[ToolEvent] = []
        # Familia de tools de "contexto GUI": si una cláusula abrió/enfocó algo,
        # las cláusulas SIGUIENTES están en ese mismo contexto y deben poder
        # actuar sobre él (escribir/clickear), aunque solas el router las trataría
        # como charla. Es la desambiguación-por-contexto: en un comando compuesto
        # ("abrí Notepad Y escribí X") sabemos que NO es smalltalk.
        _GUI_CTX = {"app", "gui", "window", "uia", "steam", "browser", "office"}
        carry: list[str] = []  # tools de contexto GUI que arrastra la cláusula previa
        carry_window: str = ""  # nombre de la app/ventana abierta por la cláusula previa
        carry_target: str = ""  # ENTIDAD/app target de la cláusula previa (p.ej. "VLC"
        #                         tras "instalá VLC") -> referente de "abrilo/lanzalo"
        # CHECKPOINT de misión (Fase 7): persistir progreso clause-by-clause para
        # poder reanudar si la misión se interrumpe (crash/reinicio/cancel). Solo
        # para misiones de varios pasos. Best-effort, no bloquea.
        _mission_id = None
        try:
            from .. import mission_checkpoint as _mc
            _mission_id = _mc.begin(self.state.path, list(clauses))
        except Exception:
            _mc = None  # type: ignore
        # resetear el presupuesto de visión de la cascada al empezar la misión
        # (Fase 8: ≤2 escalaciones de visión por misión).
        try:
            from .. import gui_vision_gate as _gvg
            _gvg.reset_budget()
        except Exception:
            pass
        # PARAR-EN-FALLO: si un paso de la cadena falla, cortamos y dejamos el
        # checkpoint SIN borrar (para reanudar). Este flag se lo dice al finally.
        _chain_failed = False
        try:
            for _clause_idx, clause in enumerate(clauses):
                # MACRO DETERMINISTA (Fase 2): si arrastramos contexto GUI y la
                # cláusula es "escribí/tecleá <texto>", NO le pedimos al 4B que
                # forme la llamada (no lo hace fiable con verbos ambiguos). El
                # código teclea directo en la ventana activa con type_into, que
                # verifica el efecto. El 4B dio el objetivo (el texto); el código
                # hace el cómo (Agent-S2 mixture of grounding). Universal.
                # ENCADENAMIENTO DEPENDIENTE: "instalá VLC Y ABRILO" ->
                # 'abrilo' abre el REFERENTE (VLC) de la cláusula previa. Determinista:
                # app.open(carry_target). MEDIDO: sin esto 'abrilo' leakeaba como texto
                # (package no está en el carry GUI, y 'abrilo' no es payload de escritura).
                if carry_target:
                    try:
                        from ..routing.command_splitter import is_dependent_open
                        _dep_open = is_dependent_open(clause)
                    except Exception:
                        _dep_open = False
                    if _dep_open:
                        _open_res = self.tools.execute("app", {"action": "open", "name": carry_target})
                        _open_ok = isinstance(_open_res, dict) and _open_res.get("ok")
                        replies.append(f"Listo, abrí {carry_target}." if _open_ok
                                       else f"Intenté abrir {carry_target} pero no pude confirmarlo.")
                        all_events.append(ToolEvent(name="app",
                            args={"action": "open", "name": carry_target},
                            result=_open_res if isinstance(_open_res, dict) else {}))
                        if _open_ok:
                            carry_window = carry_target; carry = ["app"]
                        if _mission_id and _mc is not None:
                            try: _mc.mark_done(self.state.path, _mission_id, _clause_idx, replies[-1])
                            except Exception: pass
                        continue
                _payload = None
                if carry:
                    try:
                        from ..routing.command_splitter import extract_write_payload
                        _payload = extract_write_payload(clause)
                    except Exception:
                        _payload = None
                if _payload:
                    # Pasamos el hint de ventana objetivo (la app que abrió la
                    # cláusula previa, p.ej. "bloc de notas") para que type_into
                    # enfoque ESA ventana y no escriba en la que casualmente tenga
                    # el foco (Word, un toast, etc.).
                    _ti_args = {"action": "type_into", "text": _payload}
                    if carry_window:
                        _ti_args["window"] = carry_window
                    res = self.tools.execute("gui", _ti_args)
                    ok = isinstance(res, dict) and res.get("ok")
                    changed = res.get("state_changed") if isinstance(res, dict) else None
                    # PARAR-EN-FALLO sólo ante evidencia POSITIVA de fallo: la tool
                    # erroró (ok False) o el verify MIDIÓ que nada cambió
                    # (changed is False). Un verify INCONCLUSO (changed is None) NO
                    # corta — muchas apps (calculadora) no exponen el texto tecleado
                    # por UIA ni cambian píxeles de forma medible, y cortar ahí daba
                    # falsos cortes. El verificador final (estado del SO) es el juez.
                    _step_failed = (not ok) or (changed is False)
                    if not _step_failed:
                        replies.append(f"Escribí «{_payload}».")
                    else:
                        replies.append(f"Intenté escribir «{_payload}» pero no pude "
                                       "confirmar que entró en la ventana activa.")
                    self.trace.event("multi_intent", "type_into_macro",
                                     text=_payload[:60], ok=ok, state_changed=changed)
                    if _mission_id and _mc is not None:
                        try:
                            _mc.mark_done(self.state.path, _mission_id, _clause_idx,
                                          replies[-1] if replies else "")
                        except Exception:
                            pass
                    # parar-en-fallo también en escritura (consistencia con click).
                    if _step_failed:
                        _chain_failed = True
                        if _clause_idx + 1 < len(clauses):
                            replies.append(
                                f"Paré la secuencia acá: faltaron los pasos "
                                f"{_clause_idx + 2} en adelante. Decime si reintento.")
                        self.trace.event("multi_intent", "chain_stopped_on_failure",
                                         at_clause=_clause_idx, text=_payload[:60])
                        break
                    continue
                # MACRO DETERMINISTA de CLICK (Fase B): simétrico a la escritura.
                # Si arrastramos contexto GUI y la cláusula es "apretá/clickeá/
                # tocá <X>", NO se lo pedimos al 4B (medido flojo encadenando):
                # - si <X> es una TECLA (enter, tab, esc...) -> gui.keypress.
                # - si <X> es un BOTÓN nombrado -> gui.click_button (UIA find por
                #   Name + InvokePattern + verify; OCR fallback). El 4B dio el
                #   objetivo (qué clickear); el código hace el cómo. Universal.
                _click_target = None
                if carry:
                    try:
                        from ..routing.command_splitter import extract_click_target, is_key_name
                        _click_target = extract_click_target(clause)
                    except Exception:
                        _click_target = None
                if _click_target:
                    _is_key = is_key_name(_click_target)
                    if _is_key:
                        res = self.tools.execute(
                            "gui", {"action": "keypress", "keys": _click_target})
                        _label_human = _click_target
                        _verb = "Apreté"
                    else:
                        _cb_args = {"action": "click_button", "label": _click_target}
                        if carry_window:
                            _cb_args["window"] = carry_window
                        res = self.tools.execute("gui", _cb_args)
                        _label_human = _click_target
                        _verb = "Cliqueé"
                    ok = isinstance(res, dict) and res.get("ok")
                    changed = res.get("state_changed") if isinstance(res, dict) else None
                    # Cortar SÓLO ante fallo positivo (ok False o changed medido
                    # False). Inconcluso (None) NO corta. EXCEPCIÓN keypress
                    # (decisión RED): una pulsación de tecla (Enter/Tab/
                    # Esc) casi nunca produce un cambio de PÍXELES medible — el
                    # frame-diff da changed=False aunque la tecla SÍ funcionó (Enter
                    # en calc/Notepad: el display ya mostraba el parcial / sólo baja
                    # una línea). Tratar keypress como BEST-EFFORT: nunca corta la
                    # cadena por su verify; el verificador final (estado del SO)
                    # juzga. Para click_button sí cortamos ante fallo medido (un
                    # botón que no se clickeó es un fallo real).
                    if _is_key:
                        _step_failed = not ok  # sólo si la tool misma erroró
                    else:
                        _step_failed = (not ok) or (changed is False)
                    if not _step_failed:
                        replies.append(f"{_verb} «{_label_human}».")
                    else:
                        replies.append(f"Intenté {_verb.lower()[:-1]}r «{_label_human}» "
                                       "pero no pude confirmar el efecto.")
                    self.trace.event("multi_intent", "click_macro",
                                     label=_click_target[:60], ok=ok,
                                     state_changed=changed,
                                     key=is_key_name(_click_target))
                    if _mission_id and _mc is not None:
                        try:
                            _mc.mark_done(self.state.path, _mission_id, _clause_idx,
                                          replies[-1] if replies else "")
                        except Exception:
                            pass
                    # PARAR-EN-FALLO (decisión RED): cortar la cadena sólo ante
                    # evidencia positiva de fallo y avisar qué quedó. El checkpoint
                    # NO se borra (finally respeta _chain_failed) -> reanudable.
                    if _step_failed:
                        _chain_failed = True
                        if _clause_idx + 1 < len(clauses):
                            replies.append(
                                f"Paré la secuencia acá: faltaron los pasos "
                                f"{_clause_idx + 2} en adelante. Decime si reintento.")
                        self.trace.event("multi_intent", "chain_stopped_on_failure",
                                         at_clause=_clause_idx, label=_click_target[:60])
                        break
                    continue
                # IN-APP NAV en cadena: "abrí Discord y andá al canal
                # general" -> la 2da cláusula navega DENTRO de la app abierta por la
                # 1ra; sola, el 4B la PIERDE (charla). La ruteamos a cu(goal + 'en
                # <app>'): el planner arma open_chat/open_url/etc. (MEDIDO: plan correcto
                # — open_chat para canal de Discord, open_url para web). Gate carry_window
                # (mid-chain) + nav-de-movimiento pelado (is_bare_inapp_nav excluye
                # 'abrí'=app-open y los verbos de tipeo/click ya manejados arriba).
                # GEMMA4_CHAIN_INAPP_NAV=0 lo apaga.
                _inapp_nav = False
                if carry_window:
                    import os as _os_nav
                    if _os_nav.environ.get("GEMMA4_CHAIN_INAPP_NAV", "1").strip().lower() \
                            not in {"0", "false", "no", "off"}:
                        try:
                            from ..routing.command_splitter import is_bare_inapp_nav
                            _inapp_nav = is_bare_inapp_nav(clause)
                        except Exception:
                            _inapp_nav = False
                if _inapp_nav:
                    _nav_goal = f"{clause.strip()} en {carry_window}"
                    try:
                        res = self.tools.t_computer_use({"goal": _nav_goal})
                    except Exception as exc:
                        res = {"ok": False, "error": str(exc)}
                    ok = isinstance(res, dict) and res.get("ok")
                    verified = res.get("verified") if isinstance(res, dict) else None
                    _nav_ok = bool(ok) and verified is not False
                    if _nav_ok:
                        replies.append(f"Fui a «{clause.strip()}» en {carry_window}.")
                    else:
                        replies.append(f"Intenté «{clause.strip()}» en {carry_window} "
                                       "pero no pude confirmarlo.")
                    all_events.append(ToolEvent(name="computer_use",
                        args={"goal": _nav_goal},
                        result=res if isinstance(res, dict) else {}))
                    self.trace.event("multi_intent", "inapp_nav_macro",
                                     goal=_nav_goal[:80], ok=ok, verified=verified)
                    if _mission_id and _mc is not None:
                        try: _mc.mark_done(self.state.path, _mission_id, _clause_idx, replies[-1])
                        except Exception: pass
                    if not _nav_ok:
                        _chain_failed = True
                        if _clause_idx + 1 < len(clauses):
                            replies.append(f"Paré la secuencia acá: faltaron los pasos "
                                           f"{_clause_idx + 2} en adelante. Decime si reintento.")
                        self.trace.event("multi_intent", "chain_stopped_on_failure",
                                         at_clause=_clause_idx, goal=_nav_goal[:60])
                        break
                    continue
                # CHAIN messaging a WhatsApp: "abrí WhatsApp y mandale a
                # X Y" -> la 2da cláusula es un MENSAJE a la app abierta (WhatsApp), NO
                # un email. El router solo (sin el contexto del chain) default a email
                # (MEDIDO). Gate: carry_window es WhatsApp + extract_message_to da
                # (contacto, cuerpo). Ruteamos al tool whatsapp (GUI-search del chat +
                # envío con su verificación de destinatario). GEMMA4_CHAIN_WSP=0 lo apaga.
                _wsp_msg = None
                if carry_window and "whatsapp" in carry_window.lower():
                    import os as _os_wsp
                    if _os_wsp.environ.get("GEMMA4_CHAIN_WSP", "1").strip().lower() \
                            not in {"0", "false", "no", "off"}:
                        try:
                            from ..routing.command_splitter import extract_message_to
                            _wsp_msg = extract_message_to(clause)
                        except Exception:
                            _wsp_msg = None
                if _wsp_msg and _wsp_msg[0]:
                    _wc, _wb = _wsp_msg[0].strip(), (_wsp_msg[1] or "").strip()
                    res = self.tools.execute("whatsapp",
                        {"action": "send_message", "contact": _wc, "text": _wb})
                    ok = isinstance(res, dict) and res.get("ok")
                    _status = res.get("status") if isinstance(res, dict) else None
                    if ok:
                        replies.append(f"Le mandé «{_wb}» a {_wc} por WhatsApp." if _wb
                                       else f"Abrí el chat con {_wc} en WhatsApp.")
                    elif _status == "needs_user":
                        replies.append(str(res.get("error") or "Falta info para mandar el mensaje."))
                    else:
                        replies.append(f"Intenté mandarle «{_wb}» a {_wc} por WhatsApp "
                                       "pero no pude confirmarlo.")
                    all_events.append(ToolEvent(name="whatsapp",
                        args={"action": "send_message", "contact": _wc, "text": _wb},
                        result=res if isinstance(res, dict) else {}))
                    self.trace.event("multi_intent", "chain_whatsapp",
                                     contact=_wc[:40], ok=ok, status=_status)
                    if _mission_id and _mc is not None:
                        try: _mc.mark_done(self.state.path, _mission_id, _clause_idx, replies[-1])
                        except Exception: pass
                    if not ok:
                        _chain_failed = True
                        if _clause_idx + 1 < len(clauses):
                            replies.append(f"Paré la secuencia acá: faltaron los pasos "
                                           f"{_clause_idx + 2} en adelante. Decime si reintento.")
                        break
                    continue
                # CHAIN read-screen (FLAGSHIP): tras navegar a una
                # PÁGINA (browser), "mostrame/leeme/ve las tareas" debe LEER la pantalla
                # por VISIÓN (describe_screen), NO la tool LOCAL (notes_tasks). Caso real:
                # "entrá a Canvas y mostrame las tareas" -> "las tareas" caía a notes_tasks
                # en vez de leer la página de Canvas. Gate: carry incluye browser +
                # is_read_screen_request (verbos visuales). GEMMA4_CHAIN_READ=0.
                _read_scr = False
                if carry and any("browser" in str(_c) for _c in carry):
                    import os as _os_rd
                    if _os_rd.environ.get("GEMMA4_CHAIN_READ", "1").strip().lower() \
                            not in {"0", "false", "no", "off"}:
                        try:
                            from ..routing.command_splitter import is_read_screen_request
                            _read_scr = is_read_screen_request(clause)
                        except Exception:
                            _read_scr = False
                if _read_scr:
                    res = self.tools.execute("vision",
                        {"action": "describe_screen", "target": clause.strip()})
                    ok = isinstance(res, dict) and res.get("ok")
                    _desc = ""
                    if isinstance(res, dict):
                        _desc = str(res.get("description") or res.get("text")
                                    or res.get("answer") or res.get("summary") or "").strip()
                    replies.append(_desc if _desc else
                                   f"Miré la pantalla pero no pude leer «{clause.strip()}».")
                    all_events.append(ToolEvent(name="vision",
                        args={"action": "describe_screen", "target": clause.strip()},
                        result=res if isinstance(res, dict) else {}))
                    self.trace.event("multi_intent", "chain_read_screen",
                                     target=clause.strip()[:60], ok=ok)
                    if _mission_id and _mc is not None:
                        try: _mc.mark_done(self.state.path, _mission_id, _clause_idx, replies[-1])
                        except Exception: pass
                    continue
                # Propagar el contexto GUI de la cláusula anterior a ESTA, para
                # que "escribí X" tras "abrí Notepad" herede gui/window y no
                # caiga a 'session' (charla). Bypassa el veto conversacional del
                # abstain head SOLO en multi-intent (sabemos que es continuación).
                self._mi_carry_tools = list(carry)
                try:
                    r = self.run_content(clause, progress=progress)
                except Exception as exc:
                    replies.append(f"(no pude con «{clause}»: {exc})")
                    continue
                c = (getattr(r, "content", "") or "").strip()
                if c:
                    replies.append(c)
                ev = getattr(r, "tool_events", None)
                if ev:
                    all_events.extend(ev)
                # actualizar carry con las tools de contexto GUI que ESTA cláusula
                # ejecutó (para la siguiente).
                # carry de contexto GUI: de _last_executed_tools O de los tool_events de
                # ESTA cláusula. Los short-circuits (open-pelado, app-action) devuelven
                # early_reply SIN pasar por _execute_turn -> NO setean _last_executed_tools,
                # pero su ToolEvent (app/gui) SÍ está en `ev`. MEDIDO: sin esto
                # "abrí la calc, escribí 5 y ..." perdía el carry tras el open-pelado y el
                # "escribí 5" no heredaba la ventana (caía a charla "cancelo").
                _ev_names = [getattr(_e, "name", None) for _e in (ev or [])]
                ran = [n for n in (list(self._last_executed_tools or []) + _ev_names)
                       if n in _GUI_CTX]
                if ran:
                    carry = ran
                    # capturar el nombre de la app/ventana abierta para que la
                    # cláusula de escritura siguiente la enfoque (hint).
                    for _ev in (ev or []):
                        if getattr(_ev, "name", None) in _GUI_CTX:
                            _a = getattr(_ev, "args", {}) or {}
                            _nm = _a.get("name") or _a.get("query") or _a.get("title")
                            if _nm:
                                carry_window = str(_nm)
                                break
                # capturar el TARGET (app/entidad) de ESTA cláusula para resolver un
                # 'abrilo/lanzalo' siguiente. De los args de CUALQUIER tool con
                # name/query/target -> incluye `package` (instalar), que NO está en
                # _GUI_CTX pero cuyo target SÍ es el referente ("instalá VLC"->VLC).
                for _ev in (ev or []):
                    _a2 = getattr(_ev, "args", {}) or {}
                    _tg = _a2.get("name") or _a2.get("query") or _a2.get("target") or _a2.get("app")
                    if _tg and isinstance(_tg, str) and len(_tg.strip()) >= 2:
                        carry_target = _tg.strip()
                        break
                # STAGE 3 — HONESTIDAD DE LA CADENA: si la cláusula AFIRMA
                # un efecto pero NINGUNA tool exitosa lo sustenta -> FALSO ÉXITO (el 4B
                # alucinó). MEDIDO: "abrí Discord y mandá hola al canal" -> clause2 decía
                # "mandé hola" SIN correr tool. Reemplazar el reply por uno honesto y
                # PARAR la cadena (deja el checkpoint para reanudar). El finalize de cada
                # cláusula solo inyecta un hint de regen, no ablanda el reply combinado.
                # Gate GEMMA4_CHAIN_HONESTY=0.
                import os as _os_ch
                if c and _os_ch.environ.get("GEMMA4_CHAIN_HONESTY", "1").strip().lower() \
                        not in {"0", "false", "no", "off"}:
                    try:
                        from ..safety_pkg.reply_validator import is_unverified_claim as _iuc
                        _unverified = bool(_iuc(c, list(ev or [])))
                    except Exception:
                        _unverified = False
                    if _unverified:
                        _honest = f"Intenté «{clause}» pero no pude confirmar que se hiciera."
                        if replies and replies[-1] == c:
                            replies[-1] = _honest
                        else:
                            replies.append(_honest)
                        try:
                            # FIX latente: `turn_id` no existía en este scope —
                            # el NameError moría en el except y este evento
                            # JAMÁS se emitió. El id de turno de esta función
                            # es el literal "multi_intent" (como el resto).
                            self.trace.event("multi_intent", "chain_step_unverified",
                                             clause=clause[:60])
                        except Exception:
                            pass
                        _chain_failed = True
                        break   # parar la cadena; el checkpoint queda para reanudar
                if _mission_id and _mc is not None:
                    try:
                        _mc.mark_done(self.state.path, _mission_id, _clause_idx, c)
                    except Exception:
                        pass
        finally:
            self._splitting = False
            self._mi_carry_tools = []
            # misión completada -> cerrar checkpoint. Si PARAMOS POR FALLO
            # (_chain_failed) NO lo borramos: queda para reanudar los pasos
            # pendientes (decisión RED: parar y avisar qué quedó). Si fue
            # interrupción DURA (crash/kill) el finally no corre y el checkpoint
            # también queda — que es exactamente lo que queremos.
            if _mission_id and _mc is not None and not _chain_failed:
                try:
                    _mc.finish(self.state.path, _mission_id)
                except Exception:
                    pass
        combined = " ".join(replies).strip() or "Listo."
        self.trace.event("multi_intent", "split_executed",
                         clauses=clauses, replies=len(replies))
        return AgentReply(content=combined, tool_events=all_events, mission=None)

    # Sitios MUY conocidos: nombre -> URL raíz. Conjunto CERRADO y chico (no es
    # routing por keywords de idioma: es un mapeo identidad-de-sitio->dominio,
    # como las marcas del safety_hook). Para CUALQUIER otro sitio NO adivinamos
    # el dominio (le erraríamos el TLD); ahí la red determinista se abstiene y
    # deja que el flujo normal (web search -> URL real) lo resuelva.
    _KNOWN_SITES = {
        "youtube": "https://www.youtube.com", "google": "https://www.google.com",
        "gmail": "https://mail.google.com", "github": "https://github.com",
        "wikipedia": "https://www.wikipedia.org", "reddit": "https://www.reddit.com",
        "twitch": "https://www.twitch.tv", "spotify": "https://open.spotify.com",
        "netflix": "https://www.netflix.com", "amazon": "https://www.amazon.com",
        "facebook": "https://www.facebook.com", "instagram": "https://www.instagram.com",
        "whatsapp": "https://web.whatsapp.com", "x": "https://x.com",
        "twitter": "https://x.com", "chatgpt": "https://chatgpt.com",
    }

    def _extract_nav_url(self, text: str) -> str | None:
        """Extrae una URL para navegar de un texto de navegación. Acepta: (1) una
        URL/dominio EXPLÍCITO (github.com, https://...); (2) un sitio MUY conocido
        por nombre (youtube->youtube.com). Devuelve None si no hay destino claro
        (NO adivina dominios de sitios dudosos -> el TLD se erraría)."""
        import re as _re
        t = (text or "").strip().lower()
        # 1) URL/dominio explícito en el texto.
        m = _re.search(r"\b((?:https?://)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+(?:/\S*)?)",
                       t, _re.IGNORECASE)
        if m:
            cand = m.group(1)
            # filtrar falsos dominios tipo "2+2" o palabras con punto raro:
            if _re.search(r"\.[a-z]{2,}", cand, _re.IGNORECASE):
                return cand if cand.startswith(("http://", "https://")) else "https://" + cand
        # 2) sitio muy conocido por nombre (token presente).
        toks = set(_re.findall(r"[a-z0-9]+", t))
        for name, url in self._KNOWN_SITES.items():
            if name in toks:
                return url
        return None

    def _deterministic_navigate(self, text: str) -> "ToolEvent | None":
        """RED DETERMINISTA: si el turno es navegación-web de ALTA confianza y se
        puede extraer una URL/sitio, ejecuta browser.open directo (sin depender de
        que el 4B emita el tool-call) y devuelve el ToolEvent. None si no aplica
        (no es navegación clara, o no hay URL extraíble -> no adivinamos)."""
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            from ..routing.intent_router import wants_web_navigation, wants_web_store
            if not (wants_web_navigation(text) or wants_web_store(text)):
                return None
        except Exception:
            return None
        url = self._extract_nav_url(text)
        if not url:
            return None  # sin destino claro -> el flujo normal (web->URL real) decide
        args = {"action": "open", "url": url}
        try:
            result = self.tools.execute("browser", args)
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return ToolEvent(name="browser", args=args, result=result if isinstance(result, dict) else {})

    def _deterministic_media_resume(self, text: str) -> "ToolEvent | None":
        """Backstop for clear current-media resume commands when the LLM skips.

        It asks media.status to resolve against OS media state. The media tool
        resumes only if a current paused video session exists, no-ops if already
        playing, and does not open a new YouTube search.
        """
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            from ..domain_tools import _looks_like_current_video_resume_request
            if not _looks_like_current_video_resume_request(text):
                return None
        except Exception:
            return None
        args = {"action": "status", "provider": "youtube"}
        try:
            result = self.tools.execute("media", args)
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if not isinstance(result, dict):
            result = {}
        if result.get("completion_status") not in {
            "resumed_current_media",
            "current_media_already_playing",
        }:
            return None
        return ToolEvent(name="media", args=args, result=result)

    @staticmethod
    def _extract_email_fields(text: str) -> dict[str, str] | None:
        """Extrae destinatario/cuerpo de 'mandá un correo a X diciendo Y'. Solo
        devuelve algo si hay un DESTINATARIO claro (email address o un nombre tras
        'a '). El cuerpo viene tras 'diciendo/que/saying/...'. Conservador: sin
        destinatario -> None (el flujo normal/clarificación decide)."""
        import re as _re
        t = (text or "").strip()
        # destinatario: email explícito, o nombre tras "a "/"to "
        addr = _re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t)
        to = addr.group(0) if addr else ""
        if not to:
            m = _re.search(r"\b(?:a|para|to|à|an)\s+([A-Za-zÁÉÍÓÚáéíóúñ][\w.\-]*"
                           r"(?:\s+[A-Za-zÁÉÍÓÚáéíóúñ][\w.\-]*)?)", t)
            if m:
                cand = m.group(1).strip()
                # cortar en conectores que NO son parte del nombre (asunto/cuerpo).
                _stop = {"con", "diciendo", "que", "saying", "con", "and", "y",
                         "asunto", "subject", "dile"}
                parts = []
                for w in cand.split():
                    if w.lower() in _stop:
                        break
                    parts.append(w)
                cand = " ".join(parts)
                if cand and cand.lower() not in {"the", "la", "el", "un", "una"}:
                    to = cand
        if not to:
            return None
        # cuerpo: lo que sigue a "diciendo/que/saying/dile que/con el mensaje"
        body = ""
        bm = _re.search(r"\b(?:diciendo(?:\s+que)?|dile\s+que|que\s+le\s+diga|"
                        r"con\s+el\s+mensaje|saying|telling\s+(?:him|her|them)\s+that|"
                        r"con\s+el\s+texto)\s+(.+)$", t, _re.IGNORECASE)
        if bm:
            body = bm.group(1).strip()
        # asunto opcional: "con el asunto X" / "subject X"
        subject = ""
        sm = _re.search(r"\b(?:con\s+el\s+asunto|asunto|subject)\s+(.+?)(?:\s+(?:diciendo|que|con el|saying)|$)",
                        t, _re.IGNORECASE)
        if sm:
            subject = sm.group(1).strip()
        return {"to": to, "subject": subject, "body": body}

    def _deterministic_email(self, text: str) -> "ToolEvent | None":
        """RED DETERMINISTA EMAIL (backstop): si el turno pide mandar un correo
        (alta confianza, embeddings) y hay destinatario, dispara la tool `email`
        con action=send. MEDIDO: el 4B SÍ emite el tool-call de email
        de forma fiable (3/3 en vivo), así que el camino normal ya lo cubre vía
        la tool — y la tool, sin Graph token, abre el REDACTOR web pre-rellenado
        (Gmail compose) con la sesión logueada (sin enviar; el usuario confirma).
        Esta red queda como RED DE SEGURIDAD para el caso raro en que el 4B NO
        llame la tool (carga/fraseo no anticipado). Delega en la MISMA tool (una
        sola fuente de verdad para la URL de compose). None si no aplica."""
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            from ..routing.intent_router import wants_send_email
            if not wants_send_email(text):
                return None
        except Exception:
            return None
        fields = self._extract_email_fields(text)
        if not fields or not fields.get("to"):
            return None
        # Delegar en la tool email (action=send). Sin token arma+abre la compose
        # URL; con token enviaría — pero como esto es un backstop determinista y
        # enviar es irreversible, forzamos el modo compose para que
        # NUNCA mande sin que el usuario lo confirme: pasamos el destinatario/
        # asunto/cuerpo y la tool, sin token, abre el redactor. (Si hubiera token,
        # el camino normal del LLM ya habría enviado; acá preferimos la vía segura.)
        args = {
            "action": "send",
            "to": fields["to"],
            "subject": fields.get("subject") or "",
            "body": fields.get("body") or "",
        }
        try:
            result = self.tools.execute("email", args)
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if isinstance(result, dict):
            result = {**result, "email_to": fields["to"]}
        return ToolEvent(name="email", args=args,
                         result=result if isinstance(result, dict) else {})

    def _deterministic_reply(self, text: str) -> "ToolEvent | None":
        """RED DETERMINISTA RESPONDER MENSAJE (backstop): "respondele/contestale a
        X que Y" con destinatario + cuerpo CLAROS -> abre el chat de WhatsApp
        pre-rellenado (auto_send=False: NO envía; el usuario revisa y manda). El 4B
        a veces se niega ("no puedo enviar mensajes") aunque la tool esté ofrecida
        (medido). Estructural: reutiliza extract_message_to (verbo + 'a <contacto>'
        + cuerpo, multi-idioma). None si no hay destinatario (p.ej. "contestale que
        sí" sin nombre) -> el LLM pregunta a quién (honesto, no inventa)."""
        if not isinstance(text, str) or not text.strip():
            return None
        # PRECEDENCIA EMAIL (bug medido): "mandale un correo a
        # ana@gmail.com diciendo X" matchea el verbo de mensaje ("mandale") y
        # extract_message_to agarra "un correo a ana@gmail.com" como contacto ->
        # mandaba a WhatsApp a un contacto basura. Si es intención de EMAIL, esta
        # red de mensaje NO dispara (la cubre la red de email / la tool email).
        try:
            from ..routing.intent_router import wants_send_email
            if wants_send_email(text):
                return None
        except Exception:
            import logging as _logging
            _logging.getLogger(__name__).debug("extract_message_to: wants_send_email falló; sigo", exc_info=True)
        # Debe SER intención de responder/mandar mensaje (no cualquier "a X que Y").
        try:
            from ..routing.command_splitter import extract_message_to
            parsed = extract_message_to(text)
        except Exception:
            return None
        if not parsed:
            return None
        contact, body = parsed
        contact = (contact or "").strip()
        body = (body or "").strip()
        # Sin destinatario claro o sin cuerpo -> NO disparamos (el LLM pide el dato).
        if not contact or not body:
            return None
        # auto_send=False: SOLO abre el chat con el texto puesto. Enviar es
        # irreversible y el Enter va a la ventana enfocada -> lo
        # confirma el usuario. Resuelve el contacto contra el store si existe.
        args = {"action": "send_message", "contact": contact,
                "text": body, "auto_send": False}
        try:
            result = self.tools.execute("whatsapp", args)
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if isinstance(result, dict):
            result = {**result, "reply_contact": contact}
        return ToolEvent(name="whatsapp", args=args,
                         result=result if isinstance(result, dict) else {})

    def _handle_pending_suggestion(self, content: Any) -> "AgentReply | None":
        """JARVIS (inv 5): resuelve el sí/no a una oferta de automatización del
        turno anterior. Si el usuario aceptó, CREA la rutina vía routine_tool.
        Devuelve un AgentReply (short-circuit) o None si no hay oferta pendiente
        o el mensaje no es un sí/no claro. Determinista, sin LLM."""
        cand = getattr(self, "_pending_suggestion", None)
        if cand is None:
            return None
        # extraer texto plano del content (puede ser str o lista multimodal)
        text = content if isinstance(content, str) else " ".join(
            p.get("text", "") for p in content if isinstance(p, dict))
        t = (text or "").strip().lower()
        import re as _re
        # Tokenizar por palabra Unicode (NO restringir a a-z latino: eso borraba
        # cirílico/CJK/árabe y rompía el sí/no de esos idiomas). \w con re.UNICODE.
        words = set(_re.findall(r"\w+", t, _re.UNICODE))
        # Confirmación/negación = vocabulario CERRADO y diminuto -> lista
        # multilingüe es lo correcto acá (no embeddings: 1-2 palabras dan señal
        # pobre y arriesgada). Cubre los idiomas más comunes; un sí/no no
        # reconocido NO se consume (cae a None) -> el turno sigue normal (miss
        # benigno, el LLM responde). Universal por cobertura + fallback seguro.
        yes = bool(words & _JARVIS_YES)
        no = bool(words & _JARVIS_NO)
        if not (yes or no) or (yes and no):
            # mensaje ambiguo: NO consumir la oferta (el usuario cambió de tema);
            # la dejamos pendiente y seguimos el turno normal.
            return None
        self._pending_suggestion = None
        # idioma de la respuesta (inv5 multilingüe): preferir el idioma EN QUE SE
        # HIZO LA OFERTA (un "no"/"sí" pelado del próximo turno no da señal de
        # idioma fiable); si no lo tenemos, inferir del propio mensaje.
        try:
            from ..memory_pkg.pattern_miner import jarvis_phrase as _jp
            _lang = getattr(self, "_pending_suggestion_lang", "") or "es"
        except Exception:
            _lang = "es"
            _jp = lambda l, k: ""  # noqa: E731
        try:
            from ..memory_pkg.suggestion_queue import SuggestionQueue
            _q = SuggestionQueue()
        except Exception:
            _q = None
        if no:
            if _q is not None:
                try: _q.mark_rejected(cand)
                except Exception: pass
            return AgentReply(content=_jp(_lang, "rejected") or "Listo, no lo automatizo.",
                              tool_events=[], mission=None)
        # YES -> crear la rutina vía routine_tool
        rt = cand.to_routine_trigger()
        if not rt:
            return AgentReply(content=_jp(_lang, "build_fail"),
                              tool_events=[], mission=None)
        label = f"jarvis: {cand.describe('es')}"[:60]
        trigger = {"type": rt["trigger_type"]}
        if rt["trigger_type"] in ("on_app_open", "on_app_close") and rt.get("trigger_key"):
            trigger["process"] = rt["trigger_key"]
        routine_args = {"action": "create", "name": label, "created_by": "jarvis",
                        "trigger": trigger, "steps": [rt["action"]]}
        try:
            res = self.tools.execute("routine", routine_args)
            ok = isinstance(res, dict) and res.get("ok")
        except Exception:
            ok = False
        if ok:
            if _q is not None:
                try: _q.mark_accepted(cand)
                except Exception: pass
            return AgentReply(content=_jp(_lang, "accepted").format(desc=cand.describe(_lang)),
                              tool_events=[], mission=None)
        return AgentReply(content=_jp(_lang, "create_fail"),
                          tool_events=[], mission=None)

    def _handle_profile_intent(self, content: Any) -> "AgentReply | None":
        """Perfil de gustos — privacidad inspectable/borrable.
        Short-circuit determinista para "¿qué sabés de mí?" (inspect) y "olvidate de
        mis datos" (forget). Detección por EMBEDDINGS (profile_intent, no keywords).
        forget PIDE CONFIRMACIÓN antes de borrar (irreversible, las reglas del proyecto #6).
        Devuelve AgentReply o None (sigue el turno normal)."""
        if self.behavior is None:
            return None
        text = content if isinstance(content, str) else " ".join(
            p.get("text", "") for p in content if isinstance(p, dict))
        text = (text or "").strip()
        if len(text) < 4:
            return None

        # ¿Hay un forget pendiente de confirmar del turno anterior? Resolver sí/no.
        if getattr(self, "_pending_profile_forget", False):
            import re as _re
            words = set(_re.findall(r"\w+", text.lower(), _re.UNICODE))
            yes = bool(words & _JARVIS_YES)
            no = bool(words & _JARVIS_NO)
            if yes and not no:
                self._pending_profile_forget = False
                try:
                    from ..memory_pkg.taste_profile import forget as _forget
                    n = _forget(self.behavior)
                    # Borrar también los gustos finos inferidos por LLM (privacidad).
                    from ..memory_pkg.taste_reflection import forget_reflection
                    forget_reflection(self.behavior)
                except Exception:
                    n = 0
                return AgentReply(
                    content=f"Listo, borré lo que sabía de vos ({n} observaciones). "
                            "Empiezo de cero.", tool_events=[], mission=None)
            if no and not yes:
                self._pending_profile_forget = False
                return AgentReply(content="Perfecto, no borro nada.",
                                  tool_events=[], mission=None)
            # ambiguo: dejar pendiente, seguir turno normal
            return None

        try:
            from ..memory_pkg.profile_intent import detect_profile_intent
            intent = detect_profile_intent(text)
        except Exception:
            return None
        if intent is None:
            return None

        if intent == "inspect":
            try:
                from ..memory_pkg.taste_profile import inspect_text
                msg = inspect_text(self.behavior)
                # Sumar los gustos finos inferidos por LLM (si el gate está ON y hay).
                from ..memory_pkg.taste_reflection import cached_insights
                _ins = cached_insights(self.behavior)
                if _ins:
                    msg += "\nY algo que fui infiriendo: " + " ".join(i.text for i in _ins)
            except Exception:
                return None
            return AgentReply(content=msg, tool_events=[], mission=None)

        if intent == "forget":
            # NO borra directo: confirma (irreversible). Si no hay nada que borrar,
            # decirlo sin armar confirmación.
            try:
                from ..memory_pkg.taste_profile import build_profile
                if build_profile(self.behavior).is_empty():
                    return AgentReply(
                        content="No tengo datos tuyos guardados, así que no hay nada que borrar.",
                        tool_events=[], mission=None)
            except Exception:
                import logging as _logging
                _logging.getLogger(__name__).debug("forget: build_profile().is_empty() falló; sigo a confirmación", exc_info=True)
            self._pending_profile_forget = True
            return AgentReply(
                content="¿Seguro que querés que borre todo lo que aprendí sobre vos "
                        "(apps, música, hábitos)? Es irreversible. Decime sí o no.",
                tool_events=[], mission=None)
        return None

    def _guard_grounded_action_claim(self, content: str, events: "list[ToolEvent]",
                                     turn_id: str) -> str:
        """Honestidad (load-bearing, medido): reescribe un claim de acción que
        ninguna tool verificada sustenta. Estructural (mide la FORMA). Único guard
        de comportamiento conservado tras el experimento de eliminación."""
        try:
            from .agent_guards import guard_grounded_action_claim
            out, new_streak, new_last = guard_grounded_action_claim(
                content, events, turn_id,
                phrase_fires=getattr(self, "_phrase_fires", None),
                trace=self.trace,
                current_user_text=getattr(self, "_current_user_text", "") or "",
                last_fallback_user_text=getattr(self, "_last_fallback_user_text", ""),
                fallback_streak=getattr(self, "_fallback_streak", 0),
                last_router_subset=getattr(self, "_last_router_subset", []) or [],
            )
            if out != content:
                self._fallback_streak = new_streak
                self._last_fallback_user_text = new_last
            return out
        except Exception:
            return content

    def _screen_description_reply(self, events: list["ToolEvent"]) -> str | None:
        """Si una tool de visión produjo una DESCRIPCIÓN de pantalla
        (describe_screen describe directo), devolverla para usarla
        como reply — el 4B débil NO la relata fiable desde el tool-result (medido:
        respondía 'no hay instrucción' con la descripción ahí mismo). Crítico para
        un usuario no-vidente: la lectura de pantalla DEBE llegarle. Toma la
        descripción del ÚLTIMO evento de visión que la tenga."""
        for ev in reversed(events or []):
            name = getattr(ev, "name", None) or (ev.get("tool") if isinstance(ev, dict) else None)
            if name != "vision":
                continue
            res = getattr(ev, "result", None) or (ev.get("result") if isinstance(ev, dict) else {}) or {}
            desc = str(res.get("description") or "").strip()
            if desc:
                return desc
        return None

    def _maybe_proactive_suffix(self, turn_events: "list[Any] | None" = None) -> str:
        """JARVIS (inv 5): en un BREAKPOINT genuino (fin de turno CONVERSACIONAL),
        si el miner detectó una rutina del usuario y la suggestion_queue la libera
        (cooldowns OK), devuelve un OFRECIMIENTO corto para anexar al reply.
        Conservador: solo sugiere, NO crea la rutina (turno futuro con el sí).
        Best-effort: cualquier fallo -> string vacío (no rompe el turno).

        NO INTRUSIVO (auditoría 2026-06-07): si el user ACABA de ejecutar una acción
        (turn_events no vacío) está EN TAREA — colgar "por cierto, ¿automatizo X?" es
        intrusivo (síntoma reportado: "apenas abro la app actúa"). Solo ofrecemos en
        turnos conversacionales (charla/pregunta, sin tool ejecutado este turno).

        Cabe en vram4: la minería es código determinista, no usa el LLM.

        OFF por default (2026-06-07): el user quiere las sugerencias por el canal
        PROACTIVO (toast/voz mientras usa la PC), NO pegadas a una respuesta del
        chat. Esta vía queda gateada con GEMMA4_JARVIS_CHAT_OFFER=1 (default OFF)
        para no meter ruido en el chat. El canal real vive en el daemon (ver
        memory_pkg/proactive_notifier.py)."""
        if self.behavior is None:
            return ""
        import os as _os_jco
        if (_os_jco.environ.get("GEMMA4_JARVIS_CHAT_OFFER") or "").strip().lower() \
                not in {"1", "true", "yes", "on"}:
            return ""   # oferta-en-chat desactivada -> el proactivo es el canal
        # gate breakpoint: no ofrecer si el turno ejecutó acciones (user en tarea)
        if turn_events:
            return ""
        try:
            from ..memory_pkg.pattern_miner import mine_simple_patterns
            from ..memory_pkg.suggestion_queue import SuggestionQueue
            # ventana reciente (latencia + recencia): minar solo los últimos ~30 días
            # en vez de TODO el historial cada turno (auditoría: O(n) por turno). El
            # miner exige >=7 días de span igual; 30d da margen sin cargar años.
            import time as _t
            _since = int((_t.time() - 30 * 86400) * 1000)
            events = self.behavior.events(since_ms=_since)
            if len(events) < 10:  # poca señal -> ni minar (barato salir)
                return ""
            cands = mine_simple_patterns(events)
            if not cands:
                return ""
            cand = SuggestionQueue().next_suggestion(cands)
            if cand is None:
                return ""
            # recordar el patrón ofrecido para resolver el sí/no del próximo turno
            self._pending_suggestion = cand
            # oferta en el idioma del turno (inv5 multilingüe). Guardamos ese
            # idioma para responder el sí/no en el MISMO idioma (un "no" pelado
            # del próximo turno no da señal de idioma; la oferta sí la tenía).
            _lang = getattr(self, "_turn_lang", "es")
            self._pending_suggestion_lang = _lang
            from ..memory_pkg.pattern_miner import jarvis_phrase as _jp
            return _jp(_lang, "offer").format(desc=cand.describe(_lang))
        except Exception:
            return ""

    # Tools de BÚSQUEDA/LISTADO cuyo resultado suele ser un PASO INTERMEDIO
    # (el usuario quiere algo CON el resultado: abrir/reproducir/leer).
    _SEARCH_LIKE_TOOLS = frozenset({
        "filesystem", "local_search", "photo_library", "web", "browser",
        "browser_real",
    })
    # Búsquedas WEB: el "segundo paso" es AMBIGUO (puede ser navegar/abrir, o puede
    # ser que la búsqueda fuera para RESPONDER una pregunta -> sintetizar es el final).
    # Reciben un nudge distinto (ver _chaining_nudge). Bug destapado en vivo:
    # con el nudge de recurso-local, "explicame qué es Python" -> web -> el 4B se
    # descarrilaba ("no hay acción"/"listo cancelo") buscando un 2do paso inexistente.
    _WEB_SEARCH_LIKE = frozenset({"web", "browser", "browser_real"})

    def _chaining_nudge(
        self, raw_tool_calls: list[dict[str, Any]], events: list[Any],
    ) -> str | None:
        """Devuelve un nudge si la última batch fue una BÚSQUEDA exitosa con
        items (paso intermedio que el modelo chico tiende a no encadenar).

        None si no aplica (no fue búsqueda, o vino vacía -> lo maneja el honesty
        guard). Empuja a Gemma a usar el primer resultado para el segundo paso."""
        if not raw_tool_calls:
            return None
        batch_evs = events[-len(raw_tool_calls):] if events else []
        for raw_call, ev in zip(raw_tool_calls, batch_evs):
            name = (raw_call.get("function") or {}).get("name", "")
            if name not in self._SEARCH_LIKE_TOOLS:
                continue
            res = getattr(ev, "result", None)
            if not isinstance(res, dict) or not res.get("ok"):
                continue
            action = str(res.get("action") or "").casefold()
            if "search" not in action and "list" not in action and "find" not in action:
                continue
            # ¿trajo items? (paths/matches/results/files no vacíos)
            items = (res.get("matches") or res.get("paths") or res.get("results")
                     or res.get("files") or res.get("items"))
            if not items:
                continue  # vacío -> honesty guard responde "no encontré nada"
            if name in self._WEB_SEARCH_LIKE:
                # Búsqueda WEB: ofrecer las DOS salidas. El nudge de recurso-local
                # asumía "abrir SIEMPRE" y descarrilaba las preguntas conceptuales
                # (el 4B no hallaba 2do paso -> "no hay acción"/"cancelo"). Acá la
                # SÍNTESIS de los resultados es una salida válida y final.
                return (
                    "[system note] Ya tenés los resultados de la búsqueda. Elegí UNA "
                    "salida y terminá el turno: (a) si el usuario pidió ABRIR/IR a una "
                    "página, abrila con browser.open(url=...) usando `top_result_url` o "
                    "el primer resultado; (b) si pidió una EXPLICACIÓN, un DATO o una "
                    "RESPUESTA, contestá AHORA en lenguaje natural sintetizando lo que "
                    "encontraste y NO llames más herramientas. La respuesta misma ES la "
                    "acción: no informes que 'no hay acción pendiente' ni canceles."
                )
            return (
                "[system note] La búsqueda encontró resultados. Si la tarea del "
                "usuario requería un SEGUNDO paso con el resultado (abrir, "
                "reproducir, leer, mostrar), EJECUTALO ahora con la siguiente "
                "tool-call usando el primer resultado. Si el resultado trae "
                "`top_result_url`, abrilo directamente con browser.open(url=...) "
                "en vez de pedirle al usuario que inspeccione la pantalla. No te "
                "detengas en la "
                "búsqueda si el usuario pidió una acción sobre lo encontrado."
            )
        return None

    # Tools que abren/leen/reproducen UN archivo y necesitan `path`. Si el LLM
    # las llama tras un search sin copiar el path, lo rellenamos del search.
    _PATH_CONSUMER_TOOLS = frozenset({"office", "media", "filesystem", "document"})

    @staticmethod
    def _first_path_from_search_result(result: dict[str, Any]) -> str | None:
        """Extrae el primer path de un resultado de filesystem.search. Robusto a
        matches=[{path:...}], paths=[...], results=[...]."""
        for key in ("matches", "paths", "results", "files", "items"):
            items = result.get(key)
            if isinstance(items, list) and items:
                first = items[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    for pk in ("path", "fullpath", "filepath", "abspath"):
                        if isinstance(first.get(pk), str):
                            return first[pk]
        return None

    def _autorepair_path_from_search(
        self, name: str, args: dict[str, Any], events: list["ToolEvent"],
    ) -> str | None:
        """Si `name` consume un path pero args no trae uno válido, devuelve el
        primer path del filesystem.search exitoso más reciente. None si no aplica
        (no es consumer, ya tiene path válido, o no hubo search)."""
        if name not in self._PATH_CONSUMER_TOOLS:
            return None
        action = str(args.get("action") or "").casefold()
        # solo acciones que abren/leen/reproducen algo concreto
        if action not in ("open", "play", "read", "open_document", ""):
            return None
        cur = args.get("path") or args.get("file") or args.get("filepath")
        if isinstance(cur, str) and cur.strip() and ("\\" in cur or "/" in cur):
            return None  # ya tiene un path que parece absoluto -> no tocar
        # buscar el último filesystem.search OK con resultados
        for ev in reversed(events):
            if getattr(ev, "name", "") != "filesystem":
                continue
            res = getattr(ev, "result", None)
            if not isinstance(res, dict) or not res.get("ok"):
                continue
            if "search" not in str(res.get("action") or "").casefold():
                continue
            p = self._first_path_from_search_result(res)
            if p:
                # resolver a absoluto respecto al root del search si hace falta
                root = res.get("root")
                if root and not ("\\" in p[:3] or "/" in p[:1] or ":" in p[:3]):
                    from pathlib import Path as _P
                    p = str(_P(str(root)) / p)
                return p
            break
        return None

    @staticmethod
    def _paths_from_search_result(result: dict[str, Any]) -> list[str]:
        """Extract path-like strings from a filesystem.search result."""
        paths: list[str] = []
        seen: set[str] = set()
        for key in ("matches", "paths", "results", "files", "items"):
            items = result.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                path: str | None = None
                if isinstance(item, str):
                    path = item
                elif isinstance(item, dict):
                    for pk in ("path", "fullpath", "filepath", "abspath"):
                        value = item.get(pk)
                        if isinstance(value, str) and value.strip():
                            path = value
                            break
                if not path:
                    continue
                path = path.strip()
                if path and path not in seen:
                    seen.add(path)
                    paths.append(path)
        return paths

    @staticmethod
    def _search_followup_target(user_text: str) -> dict[str, str] | None:
        """Return the second-step target requested after a file search."""
        if not user_text:
            return None
        import re
        text = _fold_match(user_text)
        if re.search(
            r"\b(reproduce|reproduci|reproducir|reproducilo|play|pon|ponme)\b",
            text,
        ):
            return {
                "target_tool": "media",
                "action": "play",
                "verb": "reproducir",
            }
        if re.search(
            r"\b(lee|leer|leeme|read|mostrame|muestrame|mostrar|show)\b",
            text,
        ):
            return {
                "target_tool": "filesystem",
                "action": "read",
                "verb": "leer",
            }
        if re.search(
            r"\b(abre|abri|abrir|abrilo|abreme|abrime|open)\b",
            text,
        ):
            return {
                "target_tool": "office",
                "action": "open",
                "verb": "abrir",
            }
        return None

    @staticmethod
    def _user_requested_file_followup(user_text: str) -> bool:
        """True when the original request asked to act on a found file."""
        return Gemma4Agent._search_followup_target(user_text) is not None

    def _filesystem_search_clarification(
        self,
        events: list["ToolEvent"],
        user_text: str,
        *,
        limit: int = 5,
    ) -> dict[str, Any] | None:
        """Ask the user to choose when E4B stops after filesystem.search.

        RED chose clarification over deterministic auto-open. This fires only
        when the last executed tool is a successful filesystem.search with
        paths and the original request asked for an action over the result.
        """
        target = self._search_followup_target(user_text)
        if not events or target is None:
            return None
        last = events[-1]
        if getattr(last, "name", "") != "filesystem":
            return None
        res = getattr(last, "result", None)
        if not isinstance(res, dict) or not res.get("ok"):
            return None
        if "search" not in str(res.get("action") or "").casefold():
            return None
        paths = self._paths_from_search_result(res)
        if not paths:
            return None
        root = res.get("root")
        normalized: list[str] = []
        for path in paths:
            if root and not ("\\" in path[:3] or "/" in path[:1] or ":" in path[:3]):
                from pathlib import Path as _P
                path = str(_P(str(root)) / path)
            normalized.append(path)
        shown = normalized[:max(1, limit)]
        lines = ["Encontre estos archivos:"]
        for index, path in enumerate(shown, start=1):
            lines.append(f"{index}. {Path(path).name} - {path}")
        if len(normalized) > len(shown):
            lines.append(f"... y {len(normalized) - len(shown)} mas.")
        lines.append(
            f"Cual queres {target['verb']}? Responde con el numero o el nombre."
        )
        return {
            "content": "\n".join(lines),
            "target_tool": target["target_tool"],
            "args": {
                "action": target["action"],
                "candidates": shown,
            },
            "paths": normalized,
        }

    def _image_is_for_llm(
        self, mode: "AgentMode", tool_name: str, result: dict[str, Any],
    ) -> bool:
        """Whether a tool-produced image should be fed to the LLM this turn.

        True for genuine vision turns / visual-deliverable tools; False for an
        action tool's self-verification screenshot (see the injection site for
        the regression this prevents)."""
        # Si la tool YA produjo una descripción de texto (vision describe_screen
        # describe directo), NO re-inyectamos la imagen: el texto ya
        # está listo y re-inyectar haría que el 4B débil fumblee (re-llamar vision
        # / cancelar). El reply usa la `description` del resultado.
        if str(result.get("description") or "").strip():
            return False
        if getattr(mode, "name", "") in ("vision_action", "audio_mode"):
            return True
        if tool_name in self._VISUAL_DELIVERABLE_TOOLS:
            return True
        action = str(result.get("action") or "").casefold()
        return any(tok in action for tok in self._VISUAL_ACTIONS)

    def _image_inject_vram_safe(self, turn_id: str = "") -> bool:
        """¿Hay VRAM para cargar mmproj y procesar una imagen inline sin OOM?

        El watchdog ACTÚA. Si no es seguro, intenta reciclar el
        server (libera VRAM fragmentada + recarga limpia) y re-chequea. Devuelve
        True si es seguro inyectar la imagen, False si conviene saltarla. Sin GPU
        NVIDIA o sin watchdog -> True (no bloquear sin evidencia)."""
        wd = getattr(self, "vram_watchdog", None)
        if wd is None:
            return True
        try:
            if wd.vision_safe():
                return True
            # No es seguro: intentar reciclar el server (descarga mmproj + reload
            # limpio) y re-medir. Best-effort.
            try:
                from ..infra.llama_server import get_shared_manager
                recycled = get_shared_manager().recycle_for_vision_leak()
            except Exception:
                recycled = False
            snap = wd.snapshot(force=True)
            safe_now = wd.vision_safe()
            try:
                self.trace.event(
                    turn_id, "vram_preflight_image_inline",
                    free_mib=snap.free_mib, level=snap.level,
                    recycled=recycled, safe=safe_now)
            except Exception:
                pass
            return safe_now
        except Exception:
            # Ante un error del watchdog, NO bloquear (fail-open: el path viejo
            # inyectaba siempre; no empeoramos).
            return True

    def _inject_tool_image(self, path: Path, result: dict[str, Any]) -> None:
        if not path.exists():
            return
        text = (
            "Esta imagen fue capturada por una tool visual. "
            f"Tamano reportado: {result.get('width')}x{result.get('height')} px. "
            "Usala como evidencia visual para continuar."
        )
        self.history.append({
            "role": "user",
            "content": [image_part(path), {"type": "text", "text": text}],
        })

    def _compact_completed_history(self) -> None:
        """Keep future turns small after a completed tool cycle.

        PRE-PASS (hotfix C): before dropping tool messages,
        harvest locator-keys from tool_results and stitch them as a
        discreet breadcrumb onto the assistant reply of the same turn.
        This preserves "where did the file get saved" across turns even
        if the LLM forgot to cite it explicitly. Bug repro: create a
        PowerPoint, next turn ask "where is it" — without the breadcrumb
        the path was lost because tool messages get dropped below.

        Two-stage strategy inspired by OpenHands:
        1. Cheap pass: drop tool messages and tool_calls, shorten strings.
        2. If estimated context usage is still > 75% of context_size, ask
           Gemma 4 itself to summarize the oldest half of the conversation
           into a single 'summary so far' assistant message. The most recent
           turns are kept verbatim.

        Bypassed entirely with GEMMA4_AGENT_SUMMARIZATION=false. Stage 1 always
        runs as a safety net even when summarization is disabled.
        """
        # PRE-PASS: stitch breadcrumbs from tool_results onto the
        # following assistant reply. Idempotent: if the assistant
        # reply already mentions the locator verbatim, nothing is added.
        self.history = _stitch_breadcrumbs(self.history)

        budget = _compute_context_budget(self.config.context_size)
        compacted: list[dict[str, Any]] = []
        for msg in self.history:
            role = str(msg.get("role") or "")
            if role == "tool":
                continue
            if role == "assistant" and msg.get("tool_calls"):
                continue
            if role not in {"user", "assistant"}:
                continue
            compacted.append({"role": role, "content": _compact_history_content(msg.get("content"))})
        self.history = compacted[-budget["soft_cap_messages"]:]

        if not _summarization_enabled():
            self.history = self.history[-budget["hard_cap_messages"]:]
            return

        # Stage 2: if the cleaned-up history is still large, summarize the
        # oldest half. We keep the last `keep_tail` messages verbatim. Both
        # the byte threshold and the keep_tail scale with context_size, so a
        # 4K model summarizes early while a 200K model can keep long history.
        threshold = budget["summarize_threshold_chars"]
        estimated = sum(len(_message_text_estimate(m)) for m in self.history)
        if estimated <= threshold or len(self.history) <= budget["keep_tail_messages"] + 2:
            return
        cooldown_turns = _summarization_cooldown_turns()
        if (self._turn_counter - self._summarize_last_run_turn) < cooldown_turns:
            self.trace.event(self.trace.new_turn_id(), "summarization_cooldown_skip",
                             since_last=self._turn_counter - self._summarize_last_run_turn,
                             cooldown=cooldown_turns)
            self.history = self.history[-budget["hard_cap_messages"]:]
            return
        keep_tail = budget["keep_tail_messages"]
        head = self.history[:-keep_tail]
        tail = self.history[-keep_tail:]
        summary_text = self._summarize_history_block(head)
        if not summary_text:
            self.history = self.history[-budget["hard_cap_messages"]:]
            return
        summary_msg = {
            "role": "assistant",
            "content": f"[Conversation summary so far]\n{summary_text}",
        }
        self.history = [summary_msg, *tail]
        self._summarize_last_run_turn = self._turn_counter

    def _extract_facts(self, user_text: str, assistant_text: str) -> list[dict[str, str]]:
        """Ask Gemma to extract 0-3 small facts about the user from this turn.

        Returns a list of {key, value} dicts. Empty list when nothing is worth
        saving (the LLM is instructed to return [] for trivial turns). Best
        effort: any JSON parse failure or LLM error returns [].

        We do NOT pass the existing memory to the LLM - this is a stateless
        single-turn extraction. Dedup happens in memory.auto_save (same key
        overwrites the older value).
        """
        prompt = (
            "Extrae 0 a 3 hechos pequenos sobre el usuario de este turno. "
            "Solo extrae si son hechos persistentes y utiles para futuras "
            "conversaciones: preferencias claras (idioma, hora, dispositivos), "
            "datos personales que el usuario menciono explicitamente (nombre, "
            "rol, ubicacion), o contexto recurrente (proyecto en el que trabaja, "
            "apps que usa). NO extraigas cosas efimeras (lo que pidio en este "
            "turno, lo que estas haciendo ahora). NO inventes. Si nada califica, "
            "devuelve exactamente '[]'.\n\n"
            "Formato de respuesta: JSON array de objetos con keys 'key' (slug "
            "corto snake_case) y 'value' (frase de menos de 100 chars). "
            "Ejemplo: [{\"key\":\"idioma\",\"value\":\"prefiere espanol\"},"
            "{\"key\":\"editor\",\"value\":\"usa VS Code\"}]. Responde SOLO el "
            "array JSON, sin markdown ni texto extra.\n\n"
            f"Turno del usuario:\n{user_text[:1500]}\n\n"
            f"Respuesta del asistente:\n{assistant_text[:1500]}\n\n"
            "JSON:"
        )
        try:
            resp = self.client.chat(
                [{"role": "user", "content": prompt}],
                tools=None,
                enable_thinking=False,
                parallel_tool_calls=False,
                max_tokens=200,
                timeout_s=20.0,
            )
        except Exception as _exc:
            try:
                self.trace.event(
                    "agent", "silent_fallback",
                    component="summarize_history_block",
                    error=f"{type(_exc).__name__}: {_exc}",
                )
            except Exception:
                pass
            return []
        choices = resp.get("choices") or []
        if not choices:
            return []
        raw = str((choices[0].get("message") or {}).get("content") or "").strip()
        # sanitize_text ya está top-level (línea 18).
        cleaned = sanitize_text(raw).strip()
        # The LLM sometimes wraps in ```json ... ``` despite instructions.
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        # Try to find the array bracket if there is prose around it.
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start < 0 or end < 0 or end < start:
            return []
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        facts: list[dict[str, str]] = []
        for item in parsed[:3]:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if key and value and len(value) <= 200:
                facts.append({"key": key, "value": value})
        return facts

    def _summarize_history_block(self, messages: list[dict[str, Any]]) -> str:
        """Ask Gemma 4 to compress the given message block into ~200 words.

        Best-effort: returns '' on any LLM failure so the caller falls back
        to plain truncation.
        """
        if not messages:
            return ""
        # Render the block as plain prose; do NOT include role markers like
        # 'tool' that would confuse the summarizer.
        rendered_parts: list[str] = []
        for msg in messages:
            role = str(msg.get("role") or "user")
            text = _message_text_estimate(msg)
            if not text.strip():
                continue
            rendered_parts.append(f"{role}: {text[:1200]}")
        rendered = "\n".join(rendered_parts)[:12000]
        prompt = (
            "Resume la siguiente conversacion en espanol en aproximadamente "
            "200 palabras. Conserva: 1) lo que el usuario pidio en cada turno, "
            "2) que tools se usaron y con que resultado, 3) decisiones tomadas, "
            "4) datos concretos que el usuario aporto (paths, nombres, ids). "
            "Omite saludos, formato decorativo y razonamientos internos. "
            "Devuelve solo el resumen, sin titulos.\n\n"
            f"CONVERSACION:\n{rendered}\n\nRESUMEN:"
        )
        _summ_msgs = [{"role": "user", "content": prompt}]
        try:
            resp = self.client.chat(
                _summ_msgs,
                tools=None,
                enable_thinking=False,
                parallel_tool_calls=False,
                max_tokens=400,
                # Router mode: must name a live preset. Without this the client
                # defaults to the dead alias "gemma-4" and the router-server
                # 400s ("model 'gemma-4' not found"), so summarization silently
                # fell back to plain truncation. Text-only prompt → text preset.
                model=self._router_model_for(_summ_msgs),
                timeout_s=60.0,
            )
            choices = resp.get("choices") or []
            if not choices:
                return ""
            msg = choices[0].get("message") or {}
            summary = str(msg.get("content") or "").strip()
            # Strip any leaked thinking tags or assistant role prefix.
            # R3 cleanup: sanitize_text ya está top-level.
            return sanitize_text(summary)[:2000]
        except Exception as exc:
            self.trace.event(self.trace.new_turn_id(), "summarization_failed", error=str(exc))
            return ""

    def _compact_active_history_for_retry(self) -> None:
        """Aggressive fallback when llama-server reports context overflow.

        Uses `_compute_context_budget(context_size)` to decide how many tail
        messages to keep and how aggressively to ellipsize tool/assistant
        contents. Keeps the budget tight (~30% of `hard_cap_messages`) so
        the retry has room for the new turn.
        """
        budget = _compute_context_budget(self.config.context_size)
        tail_count = max(4, budget["hard_cap_messages"] // 3)
        ellipsize_to = max(400, budget["history_chars"] // tail_count // 2)
        trimmed: list[dict[str, Any]] = []
        for msg in self.history[-tail_count:]:
            role = str(msg.get("role") or "")
            if role == "tool":
                trimmed.append({
                    "role": "tool",
                    "tool_call_id": str(msg.get("tool_call_id") or "call_compacted"),
                    "content": _middle_ellipsis(str(msg.get("content") or ""), ellipsize_to),
                })
            elif role == "assistant":
                clean = {"role": "assistant", "content": _middle_ellipsis(str(msg.get("content") or ""), ellipsize_to)}
                if msg.get("tool_calls"):
                    clean["tool_calls"] = _compact_json(msg.get("tool_calls"), max_items=4, max_string=500)
                trimmed.append(clean)
            elif role == "user":
                trimmed.append({"role": "user", "content": _compact_history_content(msg.get("content"))})
        while trimmed and trimmed[0].get("role") == "tool":
            trimmed.pop(0)
        self.history = trimmed




# Compaction helpers moved to :mod:`.agent_compaction`. The
# original module-level names live there now; we re-import here so call
# sites inside agent.py keep working without explicit qualification.
from .agent_compaction import (  # noqa: E402,F401
    HISTORY_TEXT_LIMIT,
    LIVE_TEXT_LIMIT,
    TOOL_RESULT_LIMIT,
    compact_history_content as _compact_history_content,
    compact_json as _compact_json,
    compact_live_content as _compact_live_content,
    compact_tool_result as _compact_tool_result,
    compute_context_budget as _compute_context_budget,
    json_len as _json_len,
    message_text_estimate as _message_text_estimate,
    middle_ellipsis as _middle_ellipsis,
    stitch_breadcrumbs as _stitch_breadcrumbs,
)


# Helpers libres extraídos a agent_helpers.py (2026-06-07, ratchet archivo-dios:
# bajar agent.py bajo su techo). Re-exportados para no romper imports/tests que
# hacen  etc. y para los call-sites internos.
from .agent_helpers import (  # noqa: E402,F401
    _extract_user_text, _derive_outcome_code, _derive_args_signature,
    _fold_match, _strip_for_phrase_only, _phrase_fire_ok,
    _format_phrase_only_reply, _is_unverified_result, _META_TOOLS,
    _INFO_RETRIEVAL_TOOLS, _QUESTION_CHARS, _domain_subset,
    _messages_have_image, _should_set_pending_intent_from_reply,
    _run_with_timeout, _format_phrase_fires, _summarization_enabled,
    _summarization_cooldown_turns, _fact_extraction_enabled,
    _fact_extraction_cooldown_turns, _parallel_tools_enabled,
    _looks_like_context_overflow, _FOOTER_PATTERNS, _strip_trailing_footers,
    _parse_args, _progress,
)

# Reparación/observación del reply (idioma, info-followup, eventos del summary)
# extraída a reply_repair.py (2026-06-08, ratchet archivo-dios: bajar agent.py
# bajo su techo tras la tanda de idioma/media). Importado como módulo para los
# wrappers de la clase; re-exporto las funciones puras con sus nombres privados
# previos para no tocar los call-sites internos.
from . import reply_repair as _reply_repair  # noqa: E402
_turn_language_instruction = _reply_repair.turn_language_instruction
_reply_language_mismatch = _reply_repair.reply_language_mismatch
_is_info_followup_question = _reply_repair.is_info_followup_question
_research_tool_fallback_enabled = _reply_repair.research_tool_fallback_enabled
_contextual_info_query = _reply_repair.contextual_info_query
