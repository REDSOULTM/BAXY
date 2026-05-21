"""Agent loop: Gemma 4 decides, tools execute, results are fed back."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import AgentConfig
from .evaluator import evaluate_mission
from .llm_client import LLMClient
from .memory import MemoryStore
from .modes import AgentMode, choose_mode
from .multimodal import image_part, user_content
from .planner import MissionPlan, plan_mission, select_tool_names
from .reasoning import detect_leaked_tool_call, sanitize_assistant_message, sanitize_text
from .state import AgentState
from .tools import ToolRegistry
from .tracing import TraceLogger, summarize_content


ProgressCallback = Callable[[str, dict[str, Any]], None]


# F-005: inherit-tools safety knobs.
# TTL: si pasaron mas de 5 min entre turns, NO heredar tools del turno
# previo (user retomo la sesion tras mucho tiempo, su contexto cambio).
INHERIT_TTL_SEC = 300
# Tools nunca-heredables por safety: una respuesta corta del user
# ("ok", "si") jamas debe disparar uno de estos sin re-confirmacion.
DANGEROUS_TOOLS_NEVER_INHERIT = frozenset({
    "whatsapp", "whatsapp_send",
    "file_delete", "file_write",
    "system_shutdown", "system_logoff", "system_restart",
    "subprocess", "shell",
})


# Sprint 5b: CORE_PROMPT + TOOL_RULES + build_system_prompt + SYSTEM_PROMPT
# moved to :mod:`.agent_prompt`. Re-export keeps existing callers (tests,
# ui/, server.py /agent/system_prompt endpoint, mcp_server) working.
from .agent_prompt import (  # noqa: E402,F401
    CORE_PROMPT,
    SYSTEM_PROMPT,
    TOOL_RULES,
    build_system_prompt,
)


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
        # Sprint 7.2: TTL purge of stale closed resources on startup so
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
        from .experience import ExperienceMemory
        self.experience = ExperienceMemory(self.config.memory_path.parent / "experience.sqlite")
        self.history: list[dict[str, Any]] = []
        self._recent_recalls: list[dict[str, Any]] = []
        self._explicit_plan_text: str = ""
        self._explicit_plan_steps: list[str] = []
        self._phrase_fires: list[dict[str, Any]] = []
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
        from .personas import from_env as _persona_from_env
        self._persona = _persona_from_env()
        # TIER 1 #3: cache de microagents seleccionados a lo largo de la sesion.
        # Cuando un microagent matchea un turn, se agrega al cache y persiste
        # para siguientes turns (mantiene el KV cache caliente). agent.clear()
        # lo resetea junto con history.
        self._cached_microagents: list = []
        # TIER 1 #4: skills menu + critical block. Cacheado a nivel-instancia
        # porque el catalogo de skills es estatico (folder skills/ no cambia
        # mid-session). El KV cache del llama-server reutiliza el prefix.
        self._cached_skills_menu: str | None = None
        self._cached_skills_critical: str | None = None
        # F-005: timestamp del ultimo turn cerrado, para TTL del inherit-tools
        # path (gap > 5 min => no heredar, evita disparar tools peligrosos
        # cuando el user retoma la sesion tras mucho tiempo).
        self._last_turn_ts: float | None = None
        # 2026-05-20: the tools the PREVIOUS turn actually executed. Survives
        # history compaction (which strips tool messages), so a short
        # continuation ("subelo un poco mas") can inherit the real prior tool
        # instead of hallucinating. The history scan can't see these because
        # _compact_completed_history drops tool_calls/tool messages.
        self._last_executed_tools: list[str] = []
        # NOTE: NLI warmup at __init__ was REMOVED — it raced with the voice
        # stack (faster_whisper) loading huggingface_hub from another thread,
        # causing intermittent "cannot import name 'logging' from
        # huggingface_hub" errors on STT init. The classifier loads the NLI
        # model lazy-on-first-use; the first capability check pays the cold
        # load cost (~14s once per process), subsequent ones hit the cache.

    def _remember_executed_tools(self, events: list[ToolEvent]) -> None:
        """Record the tool names this turn actually executed, so the NEXT
        turn's continuation-inherit can use them even after the tool messages
        are compacted out of history. Only meaningful tools (skip none)."""
        names: list[str] = []
        for e in events:
            nm = getattr(e, "name", None) or getattr(e, "tool", None)
            if isinstance(nm, str) and nm and nm not in names:
                names.append(nm)
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
        # Skills cache: reset para que scan_skills() vuelva a leer disk en el
        # proximo turn (util si el dev agrega/modifica un SKILL.md durante
        # desarrollo). En produccion el catalogo no cambia mid-session.
        self._cached_skills_menu = None
        self._cached_skills_critical = None
        self._last_turn_ts = None

    def set_persona(self, name: str) -> dict[str, Any]:
        """Switch the agent's persona by name. Returns the new persona info or an error dict."""
        from .personas import PERSONAS, get
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
        mode_hint = f"\n\n# Current mode\n{mode.system_hint}" if mode else ""
        plan_hint = f"\n\n{plan.prompt_hint()}" if plan and plan.prompt_hint() else ""
        persona_hint = f"\n\n{self._persona.system_hint}" if self._persona.system_hint else ""
        from .experience import format_recall_for_prompt
        from .explicit_plan import format_for_prompt as _format_explicit_plan
        from .project_context import format_for_prompt as _format_project_context
        from .project_context import load_context
        project_block = _format_project_context(load_context())
        project_section = f"\n\n{project_block}" if project_block else ""
        recall_hint = format_recall_for_prompt(self._recent_recalls)
        recall_section = f"\n\n{recall_hint}" if recall_hint else ""
        explicit_block = _format_explicit_plan(self._explicit_plan_text)
        explicit_section = f"\n\n{explicit_block}" if explicit_block else ""
        phrase_section = _format_phrase_fires(self._phrase_fires)
        phrase_section = f"\n\n{phrase_section}" if phrase_section else ""
        # Sprint 1 / item I1 #7: bloque "Tool Schemas EXACT" del informe de
        # optimizacion. Patron Daniel Farina (OpenCode-on-Gemma-4): reduce
        # errores de tool selection y argument naming. Opt-out via env var
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
        # TIER 1 #3: microagents — markdown files con frontmatter que se
        # inyectan al system_prompt cuando user_text matchea sus triggers.
        # Diferencia ortogonal con TOOL_RULES:
        #   TOOL_RULES["X"]: como usar la tool X (regla de uso, viene con
        #     selected_tool_names).
        #   microagent: que SIGNIFICA un concepto / como diagnosticar (conoc.
        #     de dominio, viene con user_text).
        # Cache a nivel-instancia: lo que matchea en un turn persiste para
        # los siguientes (KV cache caliente entre turns relacionados).
        try:
            from .microagents import build_microagents_section
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
        # TIER 1 #4: skills menu (compact, una linea por skill) + critical
        # block (full body de skills con priority=critical). Cacheado a
        # nivel-instancia: el catalogo skills/ no cambia mid-session.
        if self._cached_skills_menu is None or self._cached_skills_critical is None:
            try:
                from .skills_registry import scan_skills, build_menu, build_critical_block
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
        # Validator hint: when the subset crosses an ambiguous pair (audio vs
        # window/browser/app/media), ask the LLM to emit an <intent> tag so
        # the dispatcher can reject obvious mismatches before they ship.
        intent_hint = ""
        if selected_tool_names:
            from .intent_validator import INTENT_TAG_INSTRUCTION, needs_intent_tag
            if needs_intent_tag(selected_tool_names):
                intent_hint = INTENT_TAG_INSTRUCTION
        return {
            "role": "system",
            "content": f"{prompt_base}{mode_hint}{tools_section}{persona_hint}{project_section}{plan_hint}{explicit_section}{recall_section}{phrase_section}{microagents_section}{skills_critical}{skills_menu}{intent_hint}\n\n# Persistent memory\n{self.memory.prompt_summary()}",
        }

    def _tool_schemas_hint(self, selected_tool_names: list[str] | None = None) -> str:
        """Construye el bloque "Tool Schemas EXACT" una sola vez por agent.

        Sprint 1 del optimization_roadmap.md. Mode seleccionado por el
        context_size del perfil activo:
          - ctx >= 32K  -> full (~11.6K tokens) — best argument fidelity.
          - ctx >= 16K  -> compact (~5.9K tokens) — descripciones cortas.
          - ctx <  16K  -> off (no hint; el catalogo nativo de tools del
                          schema en --jinja sigue siendo el camino).
        Override via GEMMA4_TOOL_SCHEMAS_HINT_MODE = full|compact|off|auto.
        Cache a nivel-instancia porque los schemas son estaticos.
        """
        import os as _os
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
            # compact: ~5.9K tokens. Activo en ctx >=12K (balanced_8gb post
            # Polish P2 que bajo de 16K -> 12K por VRAM tight) para que
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
                    from .tools import COMPOUND_TOOL_SCHEMAS, compile_tools_to_markdown_exact
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
                from .tools import compile_tools_to_markdown_exact
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
    ) -> list[dict[str, Any]]:
        return [
            self._system_message(
                mode, plan,
                selected_tool_names=selected_tool_names,
                user_text=user_text,
            ),
            *self.history,
        ]

    def run_text(
        self,
        text: str,
        images: list[Path] | None = None,
        audios: list[Path] | None = None,
        progress: ProgressCallback | None = None,
    ) -> AgentReply:
        content = user_content(text, images=images, audios=audios)
        return self.run_content(content, progress=progress)

    def run_content(self, content: str | list[dict[str, Any]], progress: ProgressCallback | None = None) -> AgentReply:
        self._turn_counter += 1
        # Allow ONE forced tool-call retry per user turn (reset here; consumed
        # in the agent loop when a domain tool was expected but none was called).
        self._forced_tool_retry_done = False
        mode = choose_mode(content, self.config.agent_mode, self.config.max_tokens)
        plan = plan_mission(content)
        turn_id = self.trace.new_turn_id()
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
            from .llama_server import resolve_turn_model, get_shared_manager
            self._router_model = resolve_turn_model(
                has_image=(mode.name == "vision_action"))
            if self._router_model is None:
                mgr = get_shared_manager()
                if mgr.is_router_mode():
                    self._router_model = mgr.router_model_for(
                        has_image=(mode.name == "vision_action"))
        except Exception:
            self._router_model = None
        # sprint2: persona is currently visible only via tool_subset.persona,
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
        # sprint2: log which microagents matched this turn (independent of
        # the cache-merge step inside _system_message). Sprint 2.1 found this
        # was unobservable in traces.jsonl.
        if raw_text_early:
            try:
                from .microagents import load_microagents, select_microagents
                _matched_ma = select_microagents(raw_text_early, load_microagents())
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
                from .domain_tools import (_looks_destructive,
                                            active_phrase_triggers)
                folded_input = _fold_match(raw_text_early)
                # Per-step timeout so a hung tool never blocks the whole turn.
                # Configurable via env; default 30s per step.
                import os as _os
                step_timeout = float(_os.environ.get("GEMMA4_PHRASE_STEP_TIMEOUT_S") or 30)
                for routine in active_phrase_triggers(self.state):
                    needle = _fold_match(str(routine.get("phrase") or ""))
                    if not needle or needle not in folded_input:
                        continue
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

        # Semantic memory: recall similar past turns. Hint-only, never blocks.
        self._recent_recalls = []
        raw_text = raw_text_early
        try:
            from .semantic_router import embed as _embed_text
            if raw_text and len(raw_text.split()) >= 2:
                # 2026-05-20 (anti-degradation): tighter than the permissive
                # default (1.2 ≈ cos 0.4). 0.9 ≈ cos 0.55 — only inject a past
                # turn that is genuinely similar. A weak match just adds prompt
                # tokens (latency) and can mislead with loosely-related
                # precedent. k stays 3 but most turns now recall 0–2.
                self._recent_recalls = self.experience.recall(
                    raw_text, embed_fn=_embed_text, k=3, max_distance=0.9)
                if self._recent_recalls:
                    self.trace.event(turn_id, "experience_recall",
                                     query=raw_text[:200],
                                     count=len(self._recent_recalls),
                                     ids=[r["id"] for r in self._recent_recalls],
                                     distances=[r["distance"] for r in self._recent_recalls])
        except Exception as exc:
            self.trace.event(turn_id, "experience_recall_failed", error=str(exc))

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
                from .explicit_plan import generate_plan, should_plan
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
        # Hotfix F 2026-05-17: pending_intent cross-turn rescue.
        # When a previous tool returned status='needs_user', the slot
        # holds the tool name so the next turn's planner and router_v2
        # can widen the subset toward it — regardless of the user's
        # reply text (language-agnostic).
        pending_intent = (
            self.state.get_pending_intent(self._turn_counter)
            if hasattr(self.state, "get_pending_intent") else None
        )
        selected_tool_names = select_tool_names(
            content, plan,
            safety_enabled=self.config.enable_safety,
            last_assistant_text=last_assistant_text,
            pending_intent=pending_intent,
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
        # ALUCINA una llamada invalida (repro 2026-05-20: "subelo un poco mas"
        # -> system({action:"audio.set_volume"}) -> invalid tool arguments).
        # 2026-05-20: antes era `if not selected_tool_names` (subset VACIO),
        # pero el planner agrega session/safety, asi que nunca disparaba para
        # continuaciones reales. Ahora dispara cuando no hay tool de dominio.
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
            # Step 5 (2026-05-21): fold the abstention decision INTO the
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
                    from .abstain_head import (
                        load_model as _ah_load, build_features as _ah_feats,
                        is_enabled as _ah_on,
                    )
                    if _ah_on():
                        _ahm = _ah_load()
                        if _ahm is not None:
                            from .intent_router import classify_intent as _ci
                            from .semantic_router import suggest_tools_scored as _sts
                            _isc = None
                            try:
                                _isc = _ci(raw_text)
                            except Exception:
                                _isc = None
                            _f = _ah_feats(raw_text, intent=_isc,
                                           scored=_sts(raw_text, k=12),
                                           keyword_fired=False)
                            # A no-tool probability at/above the routing
                            # threshold means "really conversational" — skip
                            # inheritance. Using the gate's own threshold (not a
                            # higher floor) was the dev-tuned sweet spot: it
                            # preserves the isolated no-tool keep (0.612) under
                            # inheritance while real deictic continuations
                            # ("ciérralo"/"subelo", which score LOW on abstain)
                            # still inherit the prior tool.
                            if _ahm.p_no_tool(_f) >= _ahm.threshold:
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
                    if prev_tools:
                        selected_tool_names = prev_tools[:6]
                        self.trace.event(
                            turn_id, "tools_inherited_from_continuation",
                            tools=selected_tool_names,
                            user_text=raw_text[:60],
                        )
        semantic_fallback = bool(getattr(select_tool_names, "_last_fallback_used", False))
        # Sprint 8a: router_v2 opt-in. By default this block is a no-op
        # (v2 is gated by GEMMA4_ROUTER_V2). In SHADOW mode it only
        # logs how v2 would have routed without changing v1's pick;
        # this is what we'll run during Sprint 8c's blind test. With
        # the real flag on, v2's subset REPLACES v1's; the persona
        # nudge / continuation-inherit logic below still applies on
        # top of either pick.
        try:
            from .router_v2 import is_enabled as _v2_enabled, is_shadow as _v2_shadow, route_v2
            _v2_on = _v2_enabled()
            _shadow = (not _v2_on) and _v2_shadow()  # shadow only when v1 still authoritative
            if _v2_on or _shadow:
                # Hotfix F 2026-05-17: pass pending_tool_hint so a parked
                # intent (status='needs_user' from prior turn) widens the
                # subset regardless of the user reply's wording.
                # Hotfix I 2026-05-17: also honor pending_question
                # (tool ran but emitted clarification_needed) — same
                # kwarg, the router doesn't care about the source.
                # pending_intent wins when both are set.
                _pending_tool = (pending_intent or {}).get("tool") if pending_intent else None
                if not _pending_tool and hasattr(self.state, "get_pending_question"):
                    _pq = self.state.get_pending_question(self._turn_counter)
                    if _pq:
                        _pending_tool = _pq.get("tool")
                _v2_subset, _v2_telemetry = route_v2(
                    raw_text_early or "",
                    pending_tool_hint=_pending_tool,
                )
                self.trace.event(
                    turn_id, "router_v2",
                    authoritative=_v2_on,
                    shadow=_shadow,
                    v2_subset=list(_v2_subset),
                    v1_subset=list(selected_tool_names),
                    agreement=sorted(set(_v2_subset) & set(selected_tool_names)),
                    disagreement_v2_only=sorted(set(_v2_subset) - set(selected_tool_names)),
                    disagreement_v1_only=sorted(set(selected_tool_names) - set(_v2_subset)),
                    **_v2_telemetry,
                )
                if _v2_on:
                    selected_tool_names = list(_v2_subset)
        except Exception as _v2_exc:  # noqa: BLE001 — never break a turn
            try:
                self.trace.event(turn_id, "router_v2_error", error=str(_v2_exc))
            except Exception:
                pass
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
        # The NLI-based capability classifier (Bug 1) was removed in Sprint 3a:
        # 3.2% cache hit rate over 5 days of use (vs 20% kill threshold per
        # 08_findings.md §2.10) for a 280MB mDeBERTa model + worker thread.
        # The keyword planner + semantic_router fallback remain.
        selected_schemas = self.tools.schemas_for_names(selected_tool_names)
        self.trace.event(turn_id, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas), semantic_fallback=semantic_fallback, persona=self._persona.name)
        _progress(progress, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas))

        # Reasoning-for-tools upgrade (9da4fd3). If a DOMAIN tool is in the subset
        # and the picked mode has thinking OFF, upgrade to quick_action
        # (thinking ON) — Gemma 4 emits tool-calls reliably only with reasoning
        # (E4B plain-OFF: 2-4/6 through the full agent).
        #
        # 2026-05-21: tool_choice=required + thinking-OFF was MEASURED as a way
        # to recover the 15-May golden-era ~1s pass-1 with reliability. It works
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
                if _domain_subset(list(selected_tool_names)):
                    from .modes import choose_mode as _choose_mode
                    mode = _choose_mode("quick_action", "quick_action", self.config.max_tokens)
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
            from .planner import _suggest_tools as _kw_suggest
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
                from .semantic_router import suggest_tools_semantic
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
        self.history.append({"role": "user", "content": _compact_live_content(content)})
        events: list[ToolEvent] = []
        failure_log: list[dict[str, Any]] = []
        replan_done = False

        # Loop detector: registra cada tool execution con result canonicalizado y
        # detecta 5 patrones de stuck (repeat, unknown_tool, ping_pong, circuit
        # breaker, vision_not_found). Two-tier escalation: warning -> critical.
        # Vive por-turn (un user request); se evita carry-over que confunda al
        # LLM entre preguntas distintas.
        from .loop_detection import LoopState
        loop_state = LoopState()
        loop_aborted = False  # se setea True si detectamos critical

        # Structural per-tool verifier (TIER 1 #2). Cada tool ejecutada produce
        # un VerifierOutcome (confirmed True/False/None) que se acumula y al
        # final del turn se rinde como footer honesto en el reply. Si el
        # outcome trae evidence_keys, los inyecta al loop_state para resetear
        # warning_count en progreso real (integration con TIER 1 #1).
        from . import verifiers as _verifiers_registry  # noqa: F401  registra via decorators
        from .verify_core import verify as _verify, summarize_verifiers, VerifierOutcome
        verifier_outcomes: list[VerifierOutcome] = []

        # TIER 2 #5: MissionGoal — verifier estructural por-mision (Voyager pattern).
        # Construido al inicio del turn desde el user_text crudo. Cada tool call
        # marca su contribucion al objetivo via mission_goal.update_with_tool.
        # Al final, compute_mission_outcome combina con los per-tool verifier
        # outcomes para producir un MissionOutcome con status semantico
        # (COMPLETED/PARTIAL/FAILED/TOOL_OK_VERIFIER_INCONCLUSIVE/...).
        from .mission_goal import MissionGoal as _MissionGoal
        from .mission_outcome import (
            compute_mission_outcome as _compute_mission_outcome,
            mission_footer as _mission_footer,
            build_tool_records as _build_tool_records,
        )
        mission_goal = _MissionGoal.from_user_text(raw_text_early or "")
        validator_retries_used = 0

        # Sprint 7.1: prompt_built_tokens — emit ONCE per turn (before the
        # retry loop) so we can track p50/p95 of input size. Estimation is
        # chars/4, conservative for a multilingual prompt. We materialize
        # the messages list here to measure exactly what the first chat
        # call will see; subsequent retry iterations may shrink the subset
        # but the FIRST attempt dominates the latency budget.
        try:
            _initial_messages = self._messages(
                mode, plan,
                selected_tool_names=selected_tool_names,
                user_text=raw_text_early,
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
            _msgs = self._messages(mode, plan, selected_tool_names=selected_tool_names, user_text=raw_text_early)
            # Re-resolve the router model per call: a tool may have injected an
            # image (e.g. screenshot) into history mid-turn, which forces the
            # vision preset even on a text-mode turn. See _messages_have_image.
            _call_model = self._router_model_for(_msgs)
            # SUMMARY-PASS slimming (2026-05-20 latency). After a tool has run on
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
            _pass_tools = None if _is_summary_pass else selected_schemas
            _pass_max = 160 if _is_summary_pass else mode.max_tokens
            try:
                resp = self.client.chat(
                    _msgs,
                    tools=_pass_tools,
                    enable_thinking=_think_now,
                    thinking_budget=mode.thinking_budget,
                    model=_call_model,
                    parallel_tool_calls=mode.parallel_tool_calls,
                    max_tokens=_pass_max,
                )
            except Exception as exc:
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
                            tools=selected_schemas,
                            enable_thinking=mode.enable_thinking,
                            thinking_budget=mode.thinking_budget,
                            model=self._router_model_for(_msgs_r),
                            parallel_tool_calls=mode.parallel_tool_calls,
                            max_tokens=mode.max_tokens,
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

            choice = (resp.get("choices") or [{}])[0]
            raw_msg = choice.get("message") or {}
            msg = sanitize_assistant_message(raw_msg)
            assistant_content = msg.get("content") or ""
            raw_tool_calls = msg.get("tool_calls") or []
            # Extract optional <intent> tag from content (validator). The tag
            # is stripped from the visible reply but kept on the side so the
            # tool-selection validator can compare declared intent vs chosen
            # (tool, action) pair below.
            from .intent_validator import (
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
            # RESCUE: a veces Gemma emite el tool call como TEXTO plano en
            # vez de via el mecanismo nativo (bug del template/decoder). Si
            # no hubo tool_calls y el content matchea "<tool>(args...)",
            # lo reescribimos como real tool_call antes de continuar.
            if not raw_tool_calls and assistant_content:
                try:
                    from .tools import COMPOUND_TOOL_SCHEMAS as _CTS
                    known_names = {
                        s["function"]["name"] for s in _CTS
                        if isinstance(s, dict) and isinstance(s.get("function"), dict)
                        and isinstance(s["function"].get("name"), str)
                    }
                except Exception as _exc:
                    try:
                        self.trace.event(
                            turn_id, "silent_fallback",
                            component="known_tool_names",
                            error=f"{type(_exc).__name__}: {_exc}",
                        )
                    except Exception:
                        pass
                    known_names = None
                rescued = detect_leaked_tool_call(
                    assistant_content, known_tool_names=known_names,
                )
                if rescued is not None:
                    self.trace.event(
                        turn_id, "tool_call_rescued",
                        tool=rescued["function"]["name"],
                        original_content=assistant_content[:200],
                    )
                    raw_tool_calls = [rescued]
                    # Limpiar el content para que NO se muestre al user el
                    # texto del tool call. El siguiente loop iteration
                    # ejecutara el tool real y generara el reply final.
                    assistant_content = ""
                    msg = {"role": "assistant", "content": "", "tool_calls": raw_tool_calls}
                else:
                    # Rescue MISSED. Capture the raw model text verbatim so we
                    # can calibrate the leak patterns against what THIS Gemma
                    # actually emits (vs guessing the format). Pure telemetry;
                    # no behaviour change. Grep traces for "rescue_missed".
                    self.trace.event(
                        turn_id, "rescue_missed",
                        raw_content=(assistant_content or "")[:400],
                    )

            # FORCED tool-call retry (2026-05-20, research-backed). If the
            # router put a DOMAIN tool in the subset but the model emitted no
            # tool_call (and the leak-rescue above didn't recover one), the
            # model "promised" the action in prose instead of calling — the
            # dominant SLM failure mode (arXiv:2504.19277: "uncontrolled
            # generation"; fix = constrained/structured output). We retry ONCE
            # with tool_choice:{type:any}, which makes llama.cpp's grammar
            # FORCE a tool-call. Measured lift on weak quants (E2B-Q2 went from
            # ~0% to usable). Guarded: one retry, only when a domain tool was
            # expected, never on no-tool/chat turns.
            if (not raw_tool_calls and selected_schemas
                    and len(events) == 0  # no tool ran yet this turn — a true
                    # skip, not the natural reply AFTER a tool already executed
                    and not getattr(self, "_forced_tool_retry_done", False)):
                try:
                    _domain_now = _domain_subset(list(selected_tool_names))
                except Exception:
                    _domain_now = []
                if _domain_now:
                    self._forced_tool_retry_done = True  # one per turn
                    self.trace.event(
                        turn_id, "forced_tool_retry",
                        domain_subset=_domain_now,
                        skipped_reply=(assistant_content or "")[:160],
                    )
                    _progress(progress, "forced_tool_retry", tools=len(events))
                    _msgs_f = self._messages(mode, plan,
                                             selected_tool_names=selected_tool_names,
                                             user_text=raw_text_early)
                    try:
                        resp_f = self.client.chat(
                            _msgs_f,
                            tools=selected_schemas,
                            enable_thinking=mode.enable_thinking,
                            thinking_budget=mode.thinking_budget,
                            model=self._router_model_for(_msgs_f),
                            parallel_tool_calls=mode.parallel_tool_calls,
                            max_tokens=mode.max_tokens,
                            force_tool=True,
                        )
                        choice_f = (resp_f.get("choices") or [{}])[0]
                        msg_f = sanitize_assistant_message(choice_f.get("message") or {})
                        tc_f = msg_f.get("tool_calls") or []
                        if tc_f:
                            raw_tool_calls = tc_f
                            assistant_content = ""
                            msg = {"role": "assistant", "content": "",
                                   "tool_calls": raw_tool_calls}
                            choice = choice_f
                            self.trace.event(turn_id, "forced_tool_retry_ok",
                                             tool=tc_f[0].get("function", {}).get("name"))
                        else:
                            self.trace.event(turn_id, "forced_tool_retry_empty")
                    except Exception as _fexc:  # never break the turn on retry
                        self.trace.event(turn_id, "forced_tool_retry_error",
                                         error=f"{type(_fexc).__name__}: {_fexc}")

            self.trace.event(
                turn_id,
                "llm_response",
                finish_reason=choice.get("finish_reason"),
                content_chars=len(assistant_content),
                tool_call_count=len(raw_tool_calls),
                stripped_reasoning=any(k in raw_msg for k in ("reasoning", "reasoning_content", "reasoning_details")),
            )
            _progress(
                progress,
                "llm_response",
                turn=_turn + 1,
                tool_calls=len(raw_tool_calls),
                tools=len(events),
            )

            if not raw_tool_calls:
                assistant_content = sanitize_text(assistant_content)
                assistant_content = self._guard_unverified_final(assistant_content, events)
                assistant_content = self._guard_phrase_confirm(assistant_content)
                assistant_content = self._guard_plan_status(assistant_content)
                assistant_content = self._guard_promise_without_action(
                    assistant_content, events,
                )
                # Bug 3: grounding gate. Inline morphological check catches
                # "Abrí X" / "busqué Y" / "agendé Z" claims when tool_events
                # is empty — same family as promise guard but for past-tense
                # action claims (vs future-tense promises). Async NLI check
                # also fires to feed the lesson store for future RAG hits.
                assistant_content = self._guard_grounded_action_claim(
                    assistant_content, events, turn_id,
                )
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
                mission = evaluate_mission(events, assistant_content, plan)
                # Enriquecer el mission dict legacy con el outcome estructural
                # (no rompe consumidores existentes — agrega claves nuevas).
                if isinstance(mission, dict):
                    mission["mission_goal_status"] = mission_outcome.status.value
                    mission["mission_goal_summary"] = mission_outcome.summary
                    mission["mission_goal_progress"] = [
                        mission_outcome.expected_satisfied,
                        mission_outcome.expected_total,
                    ]
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
                try:
                    from .semantic_router import embed as _embed_text
                    raw_text = _extract_user_text(content)
                    used_tools = sorted({e.name for e in events})
                    mission_status = (mission or {}).get("mission_status") if isinstance(mission, dict) else None
                    # Derive outcome_code (more specific than mission_status).
                    outcome_code = _derive_outcome_code(mission_status, events)
                    # capability_label was sourced from the NLI classifier
                    # (removed in Sprint 3a). Future RAG rows go in with
                    # capability_label=None until an alternative is wired.
                    capability_label = None
                    args_signature = _derive_args_signature(events)
                    rec = self.experience.record(
                        turn_id=turn_id,
                        user_input=raw_text,
                        tools_used=used_tools,
                        outcome=assistant_content[:1000],
                        mission_status=mission_status,
                        summary=assistant_content[:400],
                        embed_fn=_embed_text,
                        outcome_code=outcome_code,
                        capability_label=capability_label,
                        args_signature=args_signature,
                    )
                    if rec.get("ok"):
                        self.trace.event(turn_id, "experience_recorded", id=rec.get("id"))
                except Exception as exc:
                    self.trace.event(turn_id, "experience_record_failed", error=str(exc))
                # Fact extraction: opt-in via env. Cooldown so we do not call
                # the LLM every turn. Skips short / trivial turns.
                if _fact_extraction_enabled():
                    cooldown = _fact_extraction_cooldown_turns()
                    if (self._turn_counter - self._fact_extract_last_run_turn) >= cooldown:
                        raw_text_now = _extract_user_text(content)
                        if raw_text_now and len(raw_text_now.split()) >= 5:
                            try:
                                facts = self._extract_facts(raw_text_now, assistant_content)
                                if facts:
                                    save_result = self.memory.auto_save(facts)
                                    self.trace.event(turn_id, "facts_extracted",
                                                     count=len(facts),
                                                     added=save_result.get("added"),
                                                     total_auto=save_result.get("total_auto"))
                                    self._fact_extract_last_run_turn = self._turn_counter
                                else:
                                    self.trace.event(turn_id, "facts_extraction_empty")
                                    self._fact_extract_last_run_turn = self._turn_counter
                            except Exception as exc:
                                self.trace.event(turn_id, "facts_extraction_failed", error=str(exc))

                # Hotfix I 2026-05-17: pending_intent rescue when
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

                # Hotfix I 2026-05-17: telemetry for the final-
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

                # Hotfix I 2026-05-17: structural backstop for
                # 'Listo' on no-tool turns (Bug B residual). The
                # prompt does 95% of the work; this catches the
                # residual drift. Deferred-correction path: inject
                # a corrective system message AFTER the assistant's
                # bad reply so the LLM sees both in the next turn's
                # context. Gemma4Agent has no _regen_reply method,
                # and building one is out of scope for this hotfix.
                try:
                    from .reply_validator import (
                        is_listo_on_no_tool_turn as _is_listo_on_no_tool_turn,
                        LISTO_REGEN_HINT as _LISTO_REGEN_HINT,
                    )
                    if _is_listo_on_no_tool_turn(
                        assistant_content or "", list(events),
                    ):
                        self.trace.event(
                            turn_id, "reply_anti_pattern_detected",
                            pattern="listo_on_no_tool",
                        )
                        self.history.append({
                            "role": "system",
                            "content": _LISTO_REGEN_HINT,
                        })
                except Exception as _exc:  # noqa: BLE001
                    try:
                        self.trace.event(
                            turn_id, "silent_fallback",
                            component="reply_validator",
                            error=f"{type(_exc).__name__}: {_exc}",
                        )
                    except Exception:
                        pass

                self._compact_completed_history()
                _progress(progress, "final", tools=len(events), mission=mission)
                self._last_turn_ts = time.time()
                self._remember_executed_tools(events)
                return AgentReply(content=assistant_content, tool_events=events, mission=mission)

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

            image_results: list[tuple[Path, dict[str, Any]]] = []
            subset_set = set(selected_tool_names)

            # Phase 1: parse + classify all calls (no execution yet).
            prepared: list[dict[str, Any]] = []
            for raw_call in raw_tool_calls:
                fn = raw_call.get("function") or {}
                name = fn.get("name", "")
                args, parse_error = _parse_args(fn.get("arguments", {}))
                in_subset = name in subset_set
                self.trace.event(turn_id, "tool_call", name=name, args=args, in_subset=in_subset, parse_error=parse_error)
                if not in_subset:
                    self.trace.event(turn_id, "router_miss", name=name, sent=sorted(subset_set))
                # Hotfix I 2026-05-17: pre-dispatch safety hook for
                # purchase / paid-action attempts. Inspects args
                # for checkout-pattern URLs and known paid action
                # names. When safety_enabled, a hit pre-loads a
                # synthetic needs_confirmation result so the
                # dispatcher skips the real call. When safety is
                # off, only the trace event fires.
                _pre_dispatch_result: dict[str, Any] | None = None
                try:
                    from .safety_hook import evaluate_tool_call
                    _action_for_hook = ""
                    if isinstance(args, dict):
                        _action_for_hook = str(args.get("action") or "")
                    _verdict = evaluate_tool_call(
                        tool_name=name,
                        action=_action_for_hook,
                        args=args if isinstance(args, dict) else {},
                    )
                    if _verdict.get("block"):
                        self.trace.event(
                            turn_id, "safety_hook_match",
                            tool=name,
                            pattern=_verdict.get("pattern"),
                            reason=_verdict.get("reason"),
                            enforced=bool(self.config.enable_safety),
                        )
                        if self.config.enable_safety:
                            _pre_dispatch_result = {
                                "ok": False,
                                "status": "needs_confirmation",
                                "verified": False,
                                "error": "purchase_guard",
                                "reason": _verdict.get("reason"),
                                "tool": name,
                                "evidence": "safety_hook_block",
                            }
                except Exception as _exc:  # noqa: BLE001
                    try:
                        self.trace.event(
                            turn_id, "silent_fallback",
                            component="safety_hook",
                            error=f"{type(_exc).__name__}: {_exc}",
                        )
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
            if parallel_ok:
                self.trace.event(turn_id, "tools_parallel_start", count=len(prepared))
                self._execute_calls_parallel(prepared, progress, len(events), turn_id=turn_id)
            else:
                self._execute_calls_sequential(prepared, progress, len(events), turn_id=turn_id)

            # Phase 3: apply results in original order to events, history,
            # traces, failure log, image collection.
            for prep in prepared:
                name = prep["name"]
                args = prep["args"]
                raw_call = prep["raw_call"]
                result = prep.get("result") or {}
                events.append(ToolEvent(name=name, args=args, result=result))
                self.trace.event(turn_id, "tool_result", name=name, result=result)
                # sprint2: surface which skill the LLM loaded so usage reports
                # can answer "which skills earn their spot in the menu?".
                # Sprint 2.1 found no skill_load activity in any of 6727 events.
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

                # Verifier estructural per-tool (TIER 1 #2): mide el efecto real
                # post-ejecucion. confirmed=True/False/None. Si trae
                # evidence_keys (e.g. "app:Steam") los inyectamos al loop_state
                # para que reset el warning_count en progreso real.
                v_outcome = _verify(name, args, result)
                verifier_outcomes.append(v_outcome)
                # TIER 2 #5: mission_goal tracking — marca el primer expected
                # outcome cuyo kind matchee esta call (segun action/args).
                # Pasa ok del result; el confirmed real lo decide el verifier
                # arriba y se combina en compute_mission_outcome.
                mission_goal.update_with_tool(name, args, bool(result.get("ok")))
                self.trace.event(
                    turn_id, "verifier",
                    tool=name,
                    confirmed=v_outcome.confirmed,
                    reason=v_outcome.reason,
                    evidence_keys=v_outcome.evidence_keys,
                )
                if v_outcome.confirmed is True:
                    for ek in (v_outcome.evidence_keys or []):
                        loop_state.record_evidence(ek)
                # Si la tool reporto ok=True pero el verifier dice confirmed=False,
                # algo es inconsistente — vale la pena loggearlo para debug.
                if v_outcome.confirmed is False and result.get("ok"):
                    self.trace.event(
                        turn_id, "verifier_disagrees",
                        tool=name, reason=v_outcome.reason,
                    )
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

                # Hotfix F 2026-05-17: pending_intent cross-turn rescue.
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

                # Hotfix I 2026-05-17: pending_question slot. The
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
                    image_results.append((Path(str(image_path)), result))

            for image_path, result in image_results:
                _progress(progress, "image_injected", path=str(image_path))
                self._inject_tool_image(image_path, result)

            # Honesty guard: if any tool in the just-processed batch returned
            # unverified/failed/needs_verification, inject an explicit user-role
            # note so Gemma cannot silently move on as if everything succeeded.
            unverified_in_batch = [
                (raw_call.get("function") or {}).get("name", "")
                for raw_call, ev in zip(raw_tool_calls, events[-len(raw_tool_calls):])
                if _is_unverified_result(ev.result)
            ]
            if unverified_in_batch:
                summary = ", ".join(unverified_in_batch[:6])
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
                    from .explicit_plan import replan
                    revised = replan(
                        raw_text,
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
        return AgentReply(content=final, tool_events=events, mission=mission)

    # Sprint 6.4: bodies moved to :mod:`.agent_dispatch`. The wrappers
    # below adapt the agent's positional progress callback to the
    # progress_emit(event, payload) callable the pure functions take.

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
            from .llama_server import resolve_turn_model
            m = resolve_turn_model(has_image=has_image)
            if m is not None:
                return m
        except Exception:
            pass
        # Fall back to whatever was resolved at turn start.
        return getattr(self, "_router_model", None)

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

        PRE-PASS (hotfix C 2026-05-17): before dropping tool messages,
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
        from .reasoning import sanitize_text
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
        try:
            resp = self.client.chat(
                [{"role": "user", "content": prompt}],
                tools=None,
                enable_thinking=False,
                parallel_tool_calls=False,
                max_tokens=400,
                timeout_s=60.0,
            )
            choices = resp.get("choices") or []
            if not choices:
                return ""
            msg = choices[0].get("message") or {}
            summary = str(msg.get("content") or "").strip()
            # Strip any leaked thinking tags or assistant role prefix.
            from .reasoning import sanitize_text
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


    # Sprint 6: post-reply guards' bodies live in :mod:`.agent_guards`.
    # The wrappers below pull the per-instance state the pure functions
    # need and persist any mutated streak/last-text back on self.

    def _guard_unverified_final(self, content: str, events: list[ToolEvent]) -> str:
        from .agent_guards import guard_unverified_final
        return guard_unverified_final(content, events)

    def _guard_phrase_confirm(self, content: str) -> str:
        from .agent_guards import guard_phrase_confirm
        return guard_phrase_confirm(content, phrase_fires=self._phrase_fires, trace=self.trace)

    def _build_user_facing_fallback(
        self,
        *,
        reason: str,
        rejected_reply: str,
        trace_label: str,
        missing: str = "",
    ) -> str:
        from .agent_guards import build_user_facing_fallback
        out, new_streak, new_last = build_user_facing_fallback(
            reason=reason,
            rejected_reply=rejected_reply,
            trace_label=trace_label,
            missing=missing,
            current_user_text=getattr(self, "_current_user_text", "") or "",
            last_fallback_user_text=getattr(self, "_last_fallback_user_text", ""),
            fallback_streak=getattr(self, "_fallback_streak", 0),
            last_router_subset=getattr(self, "_last_router_subset", []) or [],
            trace=self.trace,
        )
        self._fallback_streak = new_streak
        self._last_fallback_user_text = new_last
        return out

    def _guard_promise_without_action(
        self, content: str, events: list[ToolEvent],
    ) -> str:
        from .agent_guards import guard_promise_without_action
        out, new_streak, new_last = guard_promise_without_action(
            content, events,
            phrase_fires=getattr(self, "_phrase_fires", None),
            trace=self.trace,
            current_user_text=getattr(self, "_current_user_text", "") or "",
            last_fallback_user_text=getattr(self, "_last_fallback_user_text", ""),
            fallback_streak=getattr(self, "_fallback_streak", 0),
            last_router_subset=getattr(self, "_last_router_subset", []) or [],
        )
        # Only persist the streak/last-text when the guard actually rebuilt
        # a fallback (i.e. when the content changed). Otherwise the streak
        # would tick on every harmless call.
        if out != content:
            self._fallback_streak = new_streak
            self._last_fallback_user_text = new_last
        return out

    def _guard_grounded_action_claim(
        self,
        content: str,
        events: list[ToolEvent],
        turn_id: str,
    ) -> str:
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

    def _guard_plan_status(self, content: str) -> str:
        from .agent_guards import guard_plan_status
        return guard_plan_status(
            content,
            explicit_plan_status=getattr(self, "_explicit_plan_status", None),
            trace=self.trace,
        )


# Sprint 6.3: compaction helpers moved to :mod:`.agent_compaction`. The
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


def _extract_user_text(content: str | list[dict[str, Any]]) -> str:
    """Return the plain-text portion of the user content (no images/audio)."""
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return " ".join(parts).strip()


def _derive_outcome_code(mission_status: str | None,
                          events: list[ToolEvent]) -> str | None:
    """Bug 2 — map (mission_status, events) → outcome_code enum.

    The codes are finite, short, and informative for RAG policy hints:
      - PASS_VERIFIED: mission_status=PASS AND at least one tool ran.
      - PASS_UNVERIFIED: PASS but no tool ran (might be smalltalk OR a
        false confirmation — disambiguate downstream via grounding flag).
      - PARTIAL: mission_status=PARTIAL.
      - FAILED: mission_status=FAILED or grounding NLI marked contradiction.
      - NEEDS_USER: mission_status=NEEDS_USER.
      - UNVERIFIED: anything else.
    """
    if not mission_status:
        return "UNVERIFIED"
    ms = str(mission_status).upper()
    if ms == "PASS":
        return "PASS_VERIFIED" if events else "PASS_UNVERIFIED"
    if ms in {"FAILED", "PARTIAL", "NEEDS_USER", "UNVERIFIED"}:
        return ms
    return ms  # passthrough for any custom status the evaluator emits


def _derive_args_signature(events: list[ToolEvent]) -> dict[str, Any] | None:
    """Bug 2 — extract normalized tool args for the lesson store.

    Captures only the most-useful, low-cardinality fields (provider, action,
    profile) — not raw queries or PII. The signature is meant to be a
    pattern the RAG can match on (e.g. provider=disney_plus), not a full
    replay of the call.
    """
    if not events:
        return None
    sig: dict[str, Any] = {}
    for ev in events:
        try:
            args = getattr(ev, "args", None) or {}
            if not isinstance(args, dict):
                continue
            for key in ("provider", "action", "engine", "browser"):
                v = args.get(key)
                if isinstance(v, str) and v and key not in sig:
                    sig[key] = v[:40]
        except Exception:
            continue
    return sig or None


def _fold_match(text: str) -> str:
    """Lowercase + drop combining marks for substring matching."""
    import unicodedata
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _is_unverified_result(result: dict[str, Any]) -> bool:
    """Return True if a tool result is failed, unverified, or needs follow-up.

    Mirrors the signals the SYSTEM_PROMPT tells Gemma to treat as 'not done':
    ok=False, verified=False, or status in {failed, needs_verification,
    attempted, needs_confirmation}. needs_user / needs_dependency are NOT
    flagged here because those require user action, not retry, and the
    failure_log filter handles them separately for replan triggering.
    """
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False:
        return True
    if result.get("verified") is False:
        return True
    status = str(result.get("status") or "").casefold()
    return status in {"failed", "needs_verification", "attempted", "needs_confirmation"}


# Hotfix I 2026-05-17. Module-level set of "meta" tools — these
# manage agent state / safety / verification rather than perform
# domain actions, so they do not count when deciding whether the
# LLM "should have called something".
_META_TOOLS: frozenset[str] = frozenset({
    "session", "state", "verify", "safety", "skill_load", "subagent",
})

# Question-mark family: ASCII, Spanish inverted, Arabic, CJK
# fullwidth. Single-char comparison; never a keyword list, so the
# detection stays language-agnostic.
_QUESTION_CHARS: frozenset[str] = frozenset({"?", "¿", "؟", "？"})


def _domain_subset(selected_tool_names: list[str]) -> list[str]:
    """Return only the non-meta tools from a router subset.

    Hotfix I 2026-05-17. Lifted to module-level for testability —
    used by both I1 (reply-shape pending_intent) and I5
    (tool_call_skipped_when_expected telemetry).
    """
    return [t for t in selected_tool_names if t not in _META_TOOLS]


def _messages_have_image(messages: list[dict[str, Any]]) -> bool:
    """True if any message carries an image part (type=='image_url').

    Router-mode lazy-vision: a TEXT turn (mode=fast_action) can still pull
    in an image MID-turn — e.g. the `gui screenshot` tool injects its capture
    back into history for visual reasoning. The follow-up LLM call then carries
    that image, so it MUST go to the vision preset (which has the mmproj), not
    the text preset. Resolving the model once per turn from mode.name misses
    this; we re-check the actual outgoing messages on every call instead.
    Bug: 'saca un screenshot' -> 500 'image input is not supported' because the
    post-screenshot summarization call was sent to <profile>-text.
    """
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


def _should_set_pending_intent_from_reply(
    reply_text: str,
    tool_calls_this_turn: list[dict[str, Any]],
    selected_tool_names: list[str],
) -> tuple[str, str] | None:
    """Decide whether to stash a pending_intent based on reply shape.

    Hotfix I 2026-05-17. Hotfix F1 already handles the case where
    a tool returns status='needs_user'. This helper covers the
    OTHER case: the LLM asked a clarifying question on its own
    (Bug D8 part 2). 100% structural — only inspects the final
    char of the trimmed reply and the structural result of any
    tool_calls. NEVER matches user text.

    Returns (tool_name, asks_for) when:
      1. Reply text trimmed ends with a question-family char
         (? ¿ ؟ ？).
      2. ZERO successful tool_calls this turn (if a tool ran
         successfully, the turn ended in a normal action — don't
         stash a pending intent on top of it).
      3. selected_tool_names has at least one non-meta tool.
    Returns None otherwise.
    """
    if not reply_text:
        return None
    # Strip trailing whitespace and common closing punctuation
    # (quotes, parens, markdown emphasis) so the trailing-char
    # check sees the real terminal punctuation.
    stripped = reply_text.rstrip().rstrip("\"'`*_)")
    if not stripped or stripped[-1] not in _QUESTION_CHARS:
        return None
    # Accept either ToolEvent dataclasses or dicts. Production
    # callers pass ToolEvent (see agent.py turn loop); unit tests
    # pass dicts for ergonomics.
    def _result_of(c: Any) -> dict[str, Any]:
        if isinstance(c, dict):
            return c.get("result") or {}
        r = getattr(c, "result", None)
        return r if isinstance(r, dict) else {}

    successful = [
        c for c in tool_calls_this_turn
        if not _is_unverified_result(_result_of(c))
    ]
    if successful:
        return None
    candidates = _domain_subset(selected_tool_names)
    if not candidates:
        return None
    return (candidates[0], "user_clarification")


def _run_with_timeout(fn: Any, *args: Any, timeout_s: float, **kwargs: Any) -> dict[str, Any]:
    """Run a sync function in a thread with a hard wall-clock timeout.

    Returns {'result': <fn return>, '_timed_out': False} on success or
    {'result': None, '_timed_out': True} when the deadline elapses.

    Implementation detail: we do NOT use ThreadPoolExecutor's context manager
    because its __exit__ joins all workers, defeating the timeout. We submit
    on a bare executor and call shutdown(wait=False) so a hanging task is
    abandoned (the thread stays alive in the background but the caller moves
    on). The thread is daemonized so it cannot block process exit.
    """
    import concurrent.futures
    import threading
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemma4_timeout")
    # Mark spawned threads as daemons so they cannot keep the process alive.
    original_factory = threading.Thread

    try:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return {"result": future.result(timeout=timeout_s), "_timed_out": False}
        except concurrent.futures.TimeoutError:
            return {"result": None, "_timed_out": True}
        except Exception as exc:
            return {"result": None, "_timed_out": False, "_error": str(exc)}
    finally:
        # Do not wait for the worker; if it's hanging, we abandon it.
        executor.shutdown(wait=False)
        _ = original_factory  # silence linters


def _format_phrase_fires(fires: list[dict[str, Any]]) -> str:
    """Render fired phrase-triggered routines for the system prompt.

    Each entry has {label, phrase, steps_run, results}. We tell Gemma the
    routine already executed and ask it to confirm briefly to the user in
    natural language. When some steps failed or timed out we add an
    explicit honesty instruction so Gemma cannot say 'done' for a step that
    actually broke.
    """
    if not fires:
        return ""
    total_steps = 0
    failed_steps = 0
    timed_out_steps = 0
    lines = ["# Phrase-triggered routines already executed this turn"]
    lines.append("These routines fired BEFORE you got the message because the user's text matched their saved phrase. Do NOT re-run their steps.")
    for fire in fires:
        label = fire.get("label") or "routine"
        phrase = fire.get("phrase") or ""
        results = fire.get("results") or []
        oks = sum(1 for r in results if r.get("ok"))
        total = len(results)
        total_steps += total
        failed_steps += total - oks
        timed_out_steps += sum(1 for r in results if r.get("timed_out"))
        lines.append(f"- {label} (phrase='{phrase}') -> {oks}/{total} steps ok")
        for r in results[:6]:
            tool = r.get("tool", "?")
            ok = r.get("ok")
            err = r.get("error") if not ok else ""
            timed_out = " (TIMED OUT)" if r.get("timed_out") else ""
            extra = f" error={err}" if err else ""
            lines.append(f"   step: tool={tool} ok={ok}{timed_out}{extra}")
    # Behavior contract.
    if failed_steps == 0:
        lines.append("All steps succeeded. Acknowledge briefly to the user in natural language what was done, then handle the rest of the message normally.")
    else:
        msg = (f"WARNING: {failed_steps} of {total_steps} steps did NOT complete"
               + (f" ({timed_out_steps} timed out)" if timed_out_steps else "")
               + ". You MUST tell the user honestly which actions did not run. "
               "Do not say 'listo', 'hecho' or 'done' for the failed steps. "
               "Either suggest a retry, ask the user to investigate, or report the error verbatim.")
        lines.append(msg)
    return "\n".join(lines)


def _summarization_enabled() -> bool:
    """Compaction by LLM summarization. Default on; disable with GEMMA4_AGENT_SUMMARIZATION=false."""
    import os
    raw = (os.environ.get("GEMMA4_AGENT_SUMMARIZATION") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _summarization_cooldown_turns() -> int:
    """Minimum number of turns between two LLM-summarization calls.

    Default 6. Override via env GEMMA4_AGENT_SUMMARIZATION_COOLDOWN.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_SUMMARIZATION_COOLDOWN") or "").strip()
    try:
        n = int(raw)
        return n if n >= 0 else 6
    except ValueError:
        return 6


def _fact_extraction_enabled() -> bool:
    """Auto fact extraction. OFF by default (privacy).

    Enable with GEMMA4_AGENT_FACT_EXTRACTION=true. When on, after each
    completed turn the agent asks Gemma to extract 0-3 small facts about
    the user (preferences, identifiers, recurring context) and saves them
    to memory with `auto:` prefix.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION") or "").strip().casefold()
    return raw in {"1", "true", "yes", "on", "si"}


def _fact_extraction_cooldown_turns() -> int:
    """Min turns between two fact-extraction LLM calls.

    Default 5. Override via env GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN") or "").strip()
    try:
        n = int(raw)
        return n if n >= 0 else 5
    except ValueError:
        return 5


def _parallel_tools_enabled() -> bool:
    """Run multiple tool calls in the same batch concurrently.

    OFF by default: most local tools share state (filesystem, registry,
    apps_index, MCP clients) and ordering can matter for the model. Enable
    explicitly with GEMMA4_AGENT_PARALLEL_TOOLS=true. When on AND the model
    emitted >=2 valid tool calls in one assistant message, they run on a
    small ThreadPoolExecutor (max_workers=4). Order is preserved when the
    results are stitched back into history.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_PARALLEL_TOOLS") or "").strip().casefold()
    return raw in {"1", "true", "yes", "on", "si"}


def _looks_like_context_overflow(message: str) -> bool:
    low = message.casefold()
    # Phrasing varies across llama-server builds: explicit "exceeds the available
    # context size" or the JSON error type "exceed_context_size_error", plus a
    # generic fallback that pairs "context size" with any "exceed*" variant.
    if "exceeds the available context size" in low:
        return True
    if "exceed_context_size_error" in low:
        return True
    return ("context size" in low) and ("exceed" in low)


# Footers added by the agent (TIER 1 #2 verifier + TIER 2 #5 mission). Si el
# LLM ve uno en el historial, lo va a reproducir en proximos turns, infando
# context + duplicando texto en pantalla. Strippeamos antes de guardar al
# history Y antes de devolver al display.
#
# 2026-05-15: user explicitly asked for "[misión: ...]" to NEVER appear. El
# patron es case-insensitive y captura variantes con / sin acento. Tambien
# detecta "Mision" (sin acento, Capitalizado) que el LLM podria emitir.
import re as _re_footers
_FOOTER_PATTERNS = [
    # "[misión: ...]" / "[Mision: ...]" — del mission_outcome
    _re_footers.compile(r"\n*\[\s*[Mm]isi[óo]n\s*:[^\]]*\]\s*$"),
    # "[N verificada(s), N no confirmada(s), N no verificable(s)]" — verifier
    _re_footers.compile(r"\n*\[\d+\s*verificada\(s\)[^\]]*\]\s*$"),
    _re_footers.compile(r"\n*\[\d+\s*no\s+confirmada\(s\)[^\]]*\]\s*$"),
    _re_footers.compile(r"\n*\[\d+\s*no\s+verificable\(s\)[^\]]*\]\s*$"),
]


def _strip_trailing_footers(text: str) -> str:
    """Remueve cualquier footer agregado por el agent del final del texto.

    Hace varias pasadas: si hay multiples footers stackeados (verifier +
    mission), los strippea todos. Idempotente (correr 2 veces da lo mismo).
    """
    if not text:
        return text
    prev = None
    cur = text.rstrip()
    while cur != prev:
        prev = cur
        for pat in _FOOTER_PATTERNS:
            cur = pat.sub("", cur).rstrip()
    return cur


def _parse_args(raw: Any) -> tuple[dict[str, Any], str | None]:
    """Parse a tool-call arguments field.

    Returns (args_dict, parse_error). parse_error is None on success; otherwise
    it's a short human-readable string suitable for surfacing to the LLM. The
    args_dict always returns something callable so the caller can still log a
    placeholder, but in the error case the caller MUST short-circuit and not
    invoke the tool with sucky data.
    """
    if isinstance(raw, dict):
        return raw, None
    if raw is None:
        return {}, None
    if isinstance(raw, str):
        raw_trim = raw.strip()
        if not raw_trim:
            return {}, None
        try:
            parsed = json.loads(raw_trim)
            if isinstance(parsed, dict):
                return parsed, None
            return {"value": parsed}, None
        except json.JSONDecodeError as exc:
            # Surface the column so Gemma can see what it sent wrong.
            preview = raw_trim if len(raw_trim) <= 200 else raw_trim[:200] + "..."
            return {"_raw_invalid_json": preview}, f"invalid_json: {exc.msg} at pos {exc.pos}"
    return {"value": raw}, f"unsupported_args_type: {type(raw).__name__}"


def _progress(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    """Forward a progress event. Errors in the user callback are swallowed
    but logged to stderr so they don't go fully silent."""
    if callback is None:
        return
    try:
        callback(event, payload)
    except Exception as exc:
        try:
            import sys
            print(f"[progress callback error in event={event}]: {exc}", file=sys.stderr)
        except Exception:
            pass
