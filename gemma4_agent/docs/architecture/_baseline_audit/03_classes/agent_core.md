# 03.08 — Agent Core (clases UML)

> **Container:** Agent Core.
> **Archivos:** `agent.py`, `subagent.py`.

## Fig 3.08 — Agent Core classes

```mermaid
classDiagram
    class ToolEvent {
        name: str
        args: dict
        result: dict
        ok: bool
        status: str
        verified: bool|None
        ts: float
        elapsed_ms: int
    }
    note for ToolEvent "@dataclass\nEvento por cada tool ejecutada"

    class AgentReply {
        content: str
        tool_events: list[ToolEvent]
        error: str|None
        mission: dict|None
    }
    note for AgentReply "@dataclass\nOutput público de run_text/run_content"

    class Gemma4Agent {
        config: AgentConfig
        memory: MemoryStore
        state: AgentState
        client: LLMClient
        tools: ToolRegistry
        experience: ExperienceMemory
        trace: TraceLogger
        history: list[dict]
        _recent_recalls: list[dict]
        _explicit_plan_text: str
        _explicit_plan_steps: list[str]
        _phrase_fires: list[dict]
        _summarize_last_run_turn: int
        _fact_extract_last_run_turn: int
        _turn_counter: int
        _explicit_plan_status: dict
        _persona: Persona
        _cached_microagents: list
        _cached_skills_menu: str|None
        _cached_skills_critical: str|None
        _last_turn_ts: float|None
        clear()
        set_persona(name) dict
        get_persona() dict
        run_text(text, images, audios, progress) AgentReply
        run_content(content, progress) AgentReply
        _system_message(mode, plan, selected_tool_names, user_text) dict
        _tool_schemas_hint(selected_tool_names) str
        _messages(content, mode, plan, selected_tool_names) list[dict]
        _execute_calls_sequential(...)
        _execute_calls_parallel(...)
        _inject_tool_image(path, result)
        _compact_completed_history()
        _compact_active_history_for_retry()
        _extract_facts(user_text, assistant_text) list[dict]
        _summarize_history_block(messages) str
        _guard_unverified_final(content, events) str
        _guard_phrase_confirm(content) str
        _build_user_facing_fallback(...)
        _guard_promise_without_action(...)
        _guard_grounded_action_claim(...)
        _guard_plan_status(content) str
    }
    note for Gemma4Agent "1 852 LOC · 21 métodos · 12 atributos privados · [GOD MÁXIMO]\nrun_content() solo = 892 LOC\n6 _guard_* methods = 337 LOC de post-reply fixups"

    Gemma4Agent o-- AgentConfig : config
    Gemma4Agent o-- MemoryStore : memory
    Gemma4Agent o-- AgentState : state
    Gemma4Agent o-- LLMClient : client
    Gemma4Agent o-- ToolRegistry : tools
    Gemma4Agent o-- ExperienceMemory : experience
    Gemma4Agent o-- TraceLogger : trace
    Gemma4Agent o-- Persona : _persona

    Gemma4Agent ..> ToolEvent : produces
    Gemma4Agent ..> AgentReply : returns
    Gemma4Agent ..> CapabilityVerdict : reads (background)
    Gemma4Agent ..> MissionPlan : reads
    Gemma4Agent ..> MissionGoal : reads
    Gemma4Agent ..> MissionOutcome : reads
    Gemma4Agent ..> VerifierOutcome : reads
    Gemma4Agent ..> IntentTag : reads
    Gemma4Agent ..> ValidationResult : reads
    Gemma4Agent ..> GroundingVerdict : reads

    ToolRegistry --> Gemma4Agent : parent_agent (back-ref para subagent)
```

## Funciones top-level (en `agent.py` fuera de la clase)

| Función / Constante | LOC | Rol |
|---|--:|---|
| `INHERIT_TTL_SEC = 300`, `DANGEROUS_TOOLS_NEVER_INHERIT = frozenset({...})` | ~10 | F-005 knobs |
| `CORE_PROMPT` (string raw multi-línea) | ~160 | El system prompt base |
| `TOOL_RULES: dict[str, str]` | ~330 | Reglas por tool inyectadas según subset |
| `build_system_prompt(selected_tool_names=None)` | ~48 | CORE + TOOL_RULES filtrado |
| `SYSTEM_PROMPT = build_system_prompt()` | 1 | Build at import time (versión "full") |
| `_extract_user_text`, `_derive_outcome_code`, `_derive_args_signature`, `_fold_match`, `_is_unverified_result`, `_run_with_timeout`, `_format_phrase_fires`, `_summarization_enabled`, `_summarization_cooldown_turns`, `_fact_extraction_enabled`, `_fact_extraction_cooldown_turns`, `_compute_context_budget`, `_parallel_tools_enabled`, `_message_text_estimate`, `_compact_live_content`, `_compact_history_content`, `_compact_tool_result`, `_compact_json` | ~410 | Helpers para `run_content` |

## Veredictos

| Clase | LOC | Métodos | Marca | Veredicto |
|---|--:|--:|---|---|
| `ToolEvent` | <30 | dataclass | — | mantener. |
| `AgentReply` | <30 | dataclass | — | mantener. |
| `Gemma4Agent` | **1 852** | 21 | `[GOD MÁXIMO]` | **#2 candidato a split del repo.** Ejes posibles: (a) extraer `_system_message` + `_tool_schemas_hint` a `agent/prompt_builder.py`, (b) extraer `_execute_calls_*` a `agent/dispatcher.py`, (c) extraer 6 `_guard_*` a `agent/guards.py`, (d) extraer `_compact_*` + `_summarize_history_block` + `_extract_facts` a `agent/history_compaction.py`. **Pero hacerlo sin tests sólidos es muy arriesgado.** |

## Hallazgos a `_findings_seed.md`

- **`Gemma4Agent` 1 852 LOC, 21 métodos, 12 atributos privados** — ya en findings (CRITICAL).
- **`run_content` 892 LOC un solo método** — ya en findings (CRITICAL).
- **6 `_guard_*` = 337 LOC de post-reply fixups** — ya en findings (HIGH).
- **`CORE_PROMPT` 160 LOC raw multi-línea en `.py`** — ya en findings (HIGH).
- **`TOOL_RULES` 330 LOC dict** — ya en findings (HIGH).
- **18 helpers top-level fuera de la clase** — ya en findings (MED).
- **`from .X import Y` lazy 6+ veces dentro de métodos** — ya en findings (MED).
