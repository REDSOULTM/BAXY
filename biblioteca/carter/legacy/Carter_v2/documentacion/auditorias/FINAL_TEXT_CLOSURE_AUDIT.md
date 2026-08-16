# Final Text Closure Audit — Carter v2

Audit date: 2026-04-30
Branch: `radical/text-closure` (HEAD `8f67917`)
Scope: read-only audit of `Carter_v2/` after the radical text-closure cycle
(F0 → F8, F-A1, F-A2, F-CATALOG, F-PROMPT, F-HONESTY, F-MEMORY,
F-CLASSIFY/F-VISION, F-SMOKE, F1 partial extraction).

---

## 1. Veredicto brutal

**Estado: CASI LISTO.** No es un parche cosmético, pero tampoco es producción-ready
todavía. La base es sana: F8 ya eliminó las listas de frases, F-PROMPT bajó el
prompt de ~17.5k a ~7.5k chars, F-CATALOG redujo el catálogo expuesto a 16 core +
top-K=64, F-A1 hizo cooperativo el cierre de procesos, F-A2 endureció la escritura
de variables de entorno, F-MEMORY saneó memoria. El smoke `F-SMOKE_smoke.json`
pasó 18/18 con Qwen3:8B real.

Lo que falta para cerrar texto:

- **Mayor riesgo actual:** [agent.py](src/carter_v2/turn/agent.py) sigue con 2 436
  LOC y `AgentEngine.run` ocupa ~778 líneas (1195–1973). Cambios en routing siguen
  necesitando intervención quirúrgica. Falta sacar los backends y el bootstrap de
  Ollama de ese archivo.
- **Mayor sobreingeniería:** tres helpers `_looks_like_*_question` viven todavía
  en [agent.py](src/carter_v2/turn/agent.py#L576-L598) devolviendo siempre `False`
  desde F8, junto con `_should_accept_text_only_first_pass` que también colapsa.
  Son ramas muertas que aún se chequean en cada turno (líneas 608-621, 1223-1225,
  1593, 1621). Además existe una carpeta basura
  [src/carter_v2/custom_types.py](src/carter_v2/custom_types.py) (sí, una carpeta
  con extensión `.py`) totalmente vacía y nunca importada.
- **Mayor fuente de latencia:** la prompt todavía inyecta el bloque
  `GUI CAPABILITIES STATUS (live)` siempre (~700 chars cuando `vision_tier=NONE`)
  y `UNIVERSAL_AGENT_KERNEL` (~672 chars) sin gating; también
  `_format_memory_facts` llama a `relevant_facts(user_text)` cada turno aunque
  no haya memoria almacenada relevante. No es brutal, pero suma 1–2k chars y
  algunos ms por turno.
- **Mayor fuente de deuda:** cuatro backends viven en `agent.py`
  (`OpenAICompatAgentBackend`, `NullAgentBackend`, `_auto_backend`,
  `_ollama_*`), en paralelo a [llama_backend.py](src/carter_v2/turn/llama_backend.py).
  El módulo `cloud_fallback.py` está separado y casi sin uso. La frontera entre
  módulos backend está sucia.

No hay evidencia de bugs activos críticos en el modo texto (smoke 18/18, pytest
limpio en HEAD). La deuda es estructural, no funcional.

---

## 2. Mapa final del sistema

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ run.py / __main__.py  ──>  carter_v2.main.main()                             │
│                                                                              │
│ main.py:  config + memory + lessons + skills + observer + capability         │
│           registry + AgentEngine + ProactiveMonitor + interfaces opcionales  │
│           (Discord/Slack/Telegram/HTTP/extension_relay, cada una behind ENV) │
│                                                                              │
│ Loop (REPL):  user_text  ──>  AgentEngine.run(...)  ──>  reply               │
└──────────────────────────────────────────────────────────────────────────────┘

AgentEngine.run (turn/agent.py, ~778 líneas) hace:

 1. brain_router.route(user_text)
       └── pure conversational shortcut (greetings ≤4-12 chars, no '?')
            ─> respuesta directa, 0 LLM, 0 tools  (turn termina)
       └── memory_save inmediato si "remember/recuerda" estructural

 2. construir contexto:
       _build_system_prompt(...)            (turn/_system_prompt.py, 7.5k chars)
         ├── kernel POLICY/MEMORY/SAFETY/RECOVERY/META-CATALOG
         ├── KNOWN FACTS         (memory.relevant_facts | list_facts)
         ├── RECENT ALERTS       (proactive.recent)
         ├── RUNTIME_DEPS        (config / backend status)
         ├── GUI CAPABILITIES    (vision_router.status, lazy desde F-CLASSIFY)
         └── UNIVERSAL_AGENT_KERNEL (~672 chars, siempre)

       _format_prior_turn_context(...)
       _active_app_context_line(...)        (si hay app activa con foco)

 3. tool_catalog_selection.select(user_text, all_tools, top_k=64)
       ├── ALWAYS_ON_CORE (16 tools)
       └── top-K bag-of-words sobre el resto

 4. iterar (max 8 iteraciones):
       backend.chat_with_tools(messages, tools)  → AgentResponse
       invariants.apply_all(...)  (IP, calendar→create, git GUI redirect)
       _execute_with_recovery(call, ...)
         └── capabilities.dispatch → CapabilityResult
       verification.verify(call, result)
       _tool_result_message(...) → append a messages

 5. finalizar:
       _guard_final_reply(...)  (no-phantom-tools)
       _sanitize_reply(...)
       _emit_turn_timing(turn_trace)        (turn/_tracing.py)

Flujo memoria
─────────────
PersistentMemory  (session/memory.py)
  ├── SQLite (.carter/memory.db, WAL, RLock)
  ├── MEMORY.md (markdown durable, dump-only en .promote_recent)
  └── relevant_facts(user_text, limit=8)  ──>  KNOWN FACTS block en prompt

Flujo GUI / percepción
─────────────────────
gui_do (capabilities/gui_agent.py, 1217 LOC)
  ├── UIA via adapters/uia.py
  ├── _gui_planner.py (decomposición multi-step)
  ├── vision_router (lazy import, F-VISION)
  └── _vision_suggestions.py (post-failure hints + actionable_next_targets)

PerceptionMonitor (turn/perception.py)  -> diff entre snapshots de pantalla/UIA

Flujo universal
───────────────
runner.py + plan_graph.py + computer_use.py
  └── Activado solo si CARTER_UNIVERSAL_PLAN_RUNNER=1
      (texto puro NO lo dispara; solo task_frame_builder lo enciende)
  └── universal/context.py inyecta UNIVERSAL_AGENT_KERNEL en TODA prompt
      (esto no está gated y es duplicación con la POLICY del kernel principal)

Flujo backend LLM
─────────────────
agent.py contiene:
  - OpenAICompatAgentBackend  (Ollama nativo + OpenAI-compat)
  - NullAgentBackend           (tests offline)
  - _auto_backend()            (autodetect Ollama / llama.cpp)
  - _ollama_*                  (probe TCP, start, env optimizations)

llama_backend.py contiene:
  - LlamaCppBackend            (in-process llama.cpp)

cloud_fallback.py contiene:
  - AnthropicCloudBackend      (sin uso real, sólo en tests)
  - OpenAICloudBackend         (sin uso real, sólo en tests)

==> Capa duplicada: hay 3 archivos haciendo "backend de LLM".
```

### Dónde se duplica lógica

1. **Prompts conversacionales:** kernel `POLICY` + `UNIVERSAL_AGENT_KERNEL` se
   pisan parcialmente (ambos dicen "no inventes, verifica con read tools").
2. **Backends:** agent.py + llama_backend.py + cloud_fallback.py.
3. **Memoria:** SQLite + MEMORY.md + KNOWN FACTS block + memory_recall tool +
   memory_remember tool. Es intencional, pero el LLM puede confundirse: hay
   tests que lo verifican y la nota en el prompt es explícita ("NEVER call
   memory_recall as a preamble"), lo cual es mismo síntoma de prompt-tapando-bug.

---

## 3. Tabla archivo por archivo

LOC = líneas reales (medidas con `Get-Content | Measure-Object -Line`).
Acción: KEEP / IMPROVE / MERGE / DELETE / OFF_BY_DEFAULT / REWRITE_SMALL / NEEDS_RUNTIME_PROOF.

### turn/

| archivo | LOC | rol actual | problema | decisión | acción propuesta | riesgo | test |
|---|---|---|---|---|---|---|---|
| [agent.py](src/carter_v2/turn/agent.py) | 2436 | AgentEngine.run + 2 backends + ollama bootstrap + 70+ helpers | gigantesco; mezcla 3 capas (control, backends, infra) | IMPROVE | extraer backends + ollama bootstrap a archivos hermanos; eliminar stubs `_looks_like_*` post-F8; fold `_should_accept_text_only_first_pass` | bajo (pure refactor) | pytest completo |
| [_system_prompt.py](src/carter_v2/turn/_system_prompt.py) | 262 | template kernel + 5 dynamic blocks + LRU | OK; bloque vision puede gating; universal block siempre activo | IMPROVE | gating `UNIVERSAL_AGENT_KERNEL` por env; medir prompt size en smoke | muy bajo | tests existentes |
| [_tracing.py](src/carter_v2/turn/_tracing.py) | ~200 | turn_trace logging | OK | KEEP | — | — | — |
| [brain_router.py](src/carter_v2/turn/brain_router.py) | ~180 | shortcut conversacional | OK; estructural | KEEP | — | — | test_brain_router_fase7.py |
| [invariants.py](src/carter_v2/turn/invariants.py) | 163 | 3 invariantes estructurales (IP/calendar/git) | OK | KEEP | — | — | test_agent_misrouting_and_memory_hardening.py |
| [engine.py](src/carter_v2/turn/engine.py) | ~300 | TurnEngine wrapper, probe snapshot | OK | KEEP | — | — | test_e2e_agent_turn.py |
| [llama_backend.py](src/carter_v2/turn/llama_backend.py) | 550 | LlamaCppBackend in-process | OK pero comparte espacio conceptual con backends en agent.py | KEEP + recibir | crear `backends/` package, mover OpenAI/Null aquí | medio | test_assistant_engine.py |
| [tool_catalog_selection.py](src/carter_v2/turn/tool_catalog_selection.py) | ~140 | F-CATALOG top-K | OK | KEEP | — | — | test_tool_routing_contracts.py |
| [verification.py](src/carter_v2/turn/verification.py) | 733 | post-tool verifiers | grande pero coherente | KEEP | revisar verifiers no usados (NEEDS_RUNTIME_PROOF) | bajo | test_verification_contracts.py |
| [perception.py](src/carter_v2/turn/perception.py) | ~300 | PerceptionMonitor | OK (usado en agent.py) | KEEP | — | — | test_observer.py |
| [intent_resolution.py](src/carter_v2/turn/intent_resolution.py) | ~180 | IntentFrame builder | poco uso evidente; revisar | NEEDS_RUNTIME_PROOF | grep + decisión | bajo | n/a |
| [ledger.py](src/carter_v2/turn/ledger.py) | ~250 | ActionLedger | OK | KEEP | — | — | test_action_ledger.py |
| [cloud_fallback.py](src/carter_v2/turn/cloud_fallback.py) | ~200 | Anthropic/OpenAI cloud backends (tests-only) | redundante con OpenAICompatAgentBackend | NEEDS_RUNTIME_PROOF | si solo tests lo usan, mover a tests/_helpers o eliminar | medio | tests que importen |
| [types.py](src/carter_v2/turn/types.py) | ~80 | dataclasses | KEEP | — | — | — | — |

### session/

| archivo | LOC | rol | decisión | acción | riesgo |
|---|---|---|---|---|---|
| [memory.py](src/carter_v2/session/memory.py) | 891 | PersistentMemory + RLock + FTS5 | KEEP | — | — |
| [proactive.py](src/carter_v2/session/proactive.py) | 652 | ProactiveMonitor + AlertQueue | KEEP | — | — |
| [skills.py](src/carter_v2/session/skills.py) | 791 | SkillLibrary | KEEP | — | — |
| [policy.py](src/carter_v2/session/policy.py) | 414 | policy gates | KEEP | — | — |
| [store.py](src/carter_v2/session/store.py) | 301 | SessionStore | KEEP | — | — |
| [observer.py](src/carter_v2/session/observer.py) | ~280 | session observer | KEEP | — | — |
| [embeddings.py](src/carter_v2/session/embeddings.py) | 227 | EmbeddingStore (Ollama nomic-embed) | KEEP_LAZY | importado lazy desde skills.py | — |
| [watchers.py](src/carter_v2/session/watchers.py) | 248 | desktop watchers | KEEP | — | — |
| [lessons.py](src/carter_v2/session/lessons.py) | ~300 | LessonLibrary | KEEP | — | — |
| [resolver.py](src/carter_v2/session/resolver.py) | ~200 | ResourceResolver | KEEP | — | — |
| [context_window.py](src/carter_v2/session/context_window.py) | ~200 | ContextBudget | KEEP | — | — |
| [critic.py](src/carter_v2/session/critic.py) | ~150 | SkillCritic | KEEP (usado en main) | — | — |
| [refs.py](src/carter_v2/session/refs.py) | ~100 | ref tracking | KEEP | — | — |
| [types.py](src/carter_v2/session/types.py) | ~80 | dataclasses | KEEP | — | — |

### capabilities/

Resumen: 44 archivos, ~12k LOC. Sin duplicados detectados. Lazy/Off bien ubicados.

- KEEP: base.py, app_resolver.py, clock.py, code.py, database.py, filesystem.py,
  memory.py, network.py, process.py, system.py, terminal.py, gui_agent.py,
  vision.py, vision_router.py (lazy), screen_cache.py, _gui_planner.py,
  _dialogs.py, _vision_suggestions.py, web.py, window.py, ui.py, input.py,
  media.py, media_files.py, calendar.py, email.py, office.py, pdf.py,
  download.py, taskman.py, scheduler.py, registry.py, notifications.py,
  meta.py, probe.py, skills.py, _graceful_close.py (F-A1), _env_persist.py
  (F-A2), _subprocess.py, _dialogs.py, desktop.py, heartbeat.py.
- KEEP_LAZY: vision_router (ya), _graceful_close, _env_persist (ya).
- OFF_BY_DEFAULT (gated por policy o env, no se importan eager en runtime
  texto): power.py (CRITICAL gate), steam.py (HIGH gate).
- NEEDS_RUNTIME_PROOF: app_uninstall (high risk, gate confirmado).

### universal/

Todos `KEEP` salvo gating de `UNIVERSAL_AGENT_KERNEL` en prompt. Activan solo si
`CARTER_UNIVERSAL_PLAN_RUNNER=1`. La inyección del kernel en TODA prompt es
gratuita en runtime de texto plano y está parcialmente duplicada con `POLICY`.

| archivo | decisión | acción |
|---|---|---|
| [context.py](src/carter_v2/universal/context.py) | IMPROVE | gate `build_universal_agent_context` con env (`CARTER_UNIVERSAL_KERNEL_PROMPT`, default OFF para texto puro) |
| resto | KEEP | — |

### recovery/

Todos KEEP. Pequeños y necesarios.

### verification/

Todos KEEP.

### interfaces/

Todos OFF_BY_DEFAULT por env (Discord, Slack, Telegram, HTTP, extension_relay).
Sólo importan al iniciar main; sin coste medible en texto puro.

| archivo | decisión |
|---|---|
| common.py / discord / slack / telegram / http_gateway / extension_relay | KEEP (gated) |

### plugins/

| archivo | decisión |
|---|---|
| [loader.py](src/carter_v2/plugins/loader.py) | KEEP (gated CARTER_ENABLE_PLUGINS) |

### tasks/

| archivo | decisión |
|---|---|
| [background.py](src/carter_v2/tasks/background.py) | KEEP (usado por download/media) |

### adapters/

| archivo | LOC | decisión | acción |
|---|---|---|---|
| [tools.py](src/carter_v2/adapters/tools.py) | 2234 | KEEP | revisar deprecated; eventual split en ~5 sub-archivos por dominio (NO en este ciclo) |
| [tool_normalizer.py](src/carter_v2/adapters/tool_normalizer.py) | ~200 | KEEP | — |
| [uia.py](src/carter_v2/adapters/uia.py) | 396 | KEEP | — |

### misc

| archivo | decisión | acción |
|---|---|---|
| [src/carter_v2/custom_types.py/](src/carter_v2/custom_types.py) | DELETE | carpeta vacía con extensión .py por error; nunca importada |
| [src/carter_v2/types.py](src/carter_v2/types.py) | KEEP | dataclasses comunes |
| [src/carter_v2/event_bus.py](src/carter_v2/event_bus.py) | KEEP | usado por observer + watchers |
| [src/carter_v2/main.py](src/carter_v2/main.py) | 978 | KEEP | hay 90 LOC de bootstrap interfaces; podrían extraerse, NO crítico |
| [src/carter_v2/config.py](src/carter_v2/config.py) | ~250 | KEEP | — |

---

## 4. Tabla función/clase crítica (agent.py)

| símbolo | líneas | rol | usado por | decisión | razón |
|---|---|---|---|---|---|
| `_strip_think_chunk` / `_strip_thinking_text` | 107-180 | strip `<think>...</think>` | streaming + finalizer | KEEP | thinking models (Qwen3) |
| `_textual_tool_calls` | 186 | parse text tool calls | iteration loop | KEEP | fallback de modelos no-tools-json |
| `_tool_call_from_json` | 230 | parse JSON call | iteration loop | KEEP | core |
| `_sanitize_reply` | 257 | normalize reply | finalizer | KEEP | core |
| `_guard_final_reply` | 292 | no-phantom-tools | finalizer | KEEP | F-HONESTY |
| `_retry_tool_hint` | 362 | "please use a tool" hint | iteration loop | KEEP | core |
| `_format_prior_turn_context` | 397 | prior turn → reference | run() | KEEP | core |
| `_active_app_context_*` (424-547) | | active-app context bias | run() | KEEP | core |
| `_looks_like_short_followup` | 448 | structural ≤20 chars | run() | KEEP | structural |
| `_resource_*` / `_span_is_explicit_switch` / `_mentions_explicit_resource_switch` / `_looks_like_resource_action_request` | 455-538 | resource detection | run() | KEEP | structural |
| `_should_reconsider_active_app` | 552 | post-tool active-app reset | run() | KEEP | core |
| `_user_text_has_explicit_level` | 558 | used by volume capability invariant | invariants/agent | KEEP | structural |
| **`_looks_like_action_request_question`** | **576** | F8 stub → False | self-only | **DELETE** | **dead, returns False always** |
| **`_looks_like_live_query_question`** | **583** | F8 stub → False | self-only + run() | **DELETE** | **dead** |
| **`_looks_like_personal_memory_query`** | **590** | F8 stub → False | self-only + run() | **DELETE** | **dead** |
| **`_should_accept_text_only_first_pass`** | **599** | trivial after stubs deleted | run() L1593 | **REWRITE_SMALL** | **fold to inline check** |
| `_is_trivially_short_input` / `_is_low_information_text_reply` | 623-644 | structural | run() | KEEP | core |
| `_active_app_gui_fallback_response` | 646 | GUI failure fallback | run() | KEEP | F-HONESTY |
| `_trace_result_data` | 662 | turn_trace formatter | _emit_turn_timing | KEEP | tracing |
| `_update_active_app_context` | 684 | active app side effect post tool | run() | KEEP | core |
| `_guess_process_name` | 740 | helper for active-app | _update_active_app_context | KEEP | core |
| `AgentResponse` | 760 | dataclass | global | KEEP | core |
| **`OpenAICompatAgentBackend`** | **775-1099** | **Ollama/OpenAI backend** | _auto_backend, run(), tests | **MERGE → backends/openai_compat.py** | **325 LOC en archivo equivocado** |
| **`NullAgentBackend`** | **1100-1126** | **null backend** | tests, _auto_backend fallback | **MERGE → backends/null.py** | **debe vivir con sus pares** |
| `AgentTurnResult` | 1128 | dataclass | run() | KEEP | core |
| `_backend_uses_compact_tools` | 1137 | detect backend feature | run() | KEEP | core |
| **`AgentEngine`** | **1147-2102** | **núcleo** | global | **KEEP / IMPROVE** | **ver run() abajo** |
| `AgentEngine.run` | 1195-1973 | turn loop | global | KEEP_HUGE | extracción de sub-fases queda como deuda explícita |
| `AgentEngine._try_universal_plan_runner` etc | 1973-2102 | universal opt-in | run() | KEEP | gated por env |
| `_env_enabled` | 2104 | helper trivial | local | KEEP | core |
| `_join_context` | 2108 | helper trivial | local | KEEP | core |
| `_task_frame_needs_universal_runner` | 2112 | universal switch | run() | KEEP | core |
| `_stable_text_fingerprint` | 2130 | hash | local | KEEP | core |
| `_resource_resolver_*` | 2134-2196 | builders | run() | KEEP | core |
| `_safe_env_path_segment` | 2165 | sanitize | local | KEEP | core |
| `_dedupe_paths` | 2171 | helper | local | KEEP | core |
| `_stable_args_hash` / `_args_summary` / `_loop_detection_message` / `_execute_tool_with_timeout` / `_execute_with_recovery` / `_backend_chat_with_tools` / `_direct_action_reply` / `_direct_result_message` / `_result_to_text` / `_tool_result_message` / `_verification_caveat` / `_append_verification_warning` | 2197-2489 | tool execution helpers | run() | KEEP | core |
| **`_ollama_available_models` / `_ollama_best_model` / `_ollama_best_draft` / `_create_speculative_modelfile` / `_auto_backend` / `_ollama_env_optimized` / `_apply_ollama_env_locally` / `_try_start_ollama` / `_tcp_probe`** | **2490-2701** | **Ollama bootstrap** | _auto_backend, main | **MERGE → backends/ollama_bootstrap.py** | **210 LOC de infra fuera del loop** |

Total LOC de agent.py recortable sólo con cambios A+B+C (sin tocar `run()`):

- Stubs F8 + fold de `_should_accept_text_only_first_pass`: ~50 LOC.
- Backends a `backends/openai_compat.py` y `backends/null.py`: ~370 LOC.
- Ollama bootstrap a `backends/ollama_bootstrap.py`: ~210 LOC.
- Total estimado: **agent.py 2 436 → ~1 800 LOC** sin tocar la lógica de `run()`.

---

## 5. Código muerto confirmado

| archivo | símbolo | evidencia | acción | rollback |
|---|---|---|---|---|
| [src/carter_v2/custom_types.py/](src/carter_v2/custom_types.py) | (carpeta entera) | grep "custom_types" → 0 hits en src+tests; carpeta vacía | DELETE | git restore |
| [agent.py](src/carter_v2/turn/agent.py#L576) | `_looks_like_action_request_question` | cuerpo `return False`; sólo se llama en L610, L1224 | DELETE + simplificar callers | git revert phase commit |
| [agent.py](src/carter_v2/turn/agent.py#L583) | `_looks_like_live_query_question` | cuerpo `return False`; L608, L1223 | DELETE + simplificar | idem |
| [agent.py](src/carter_v2/turn/agent.py#L590) | `_looks_like_personal_memory_query` | cuerpo `return False`; L612, L1225, L1621 | DELETE + simplificar | idem |
| [agent.py](src/carter_v2/turn/agent.py#L599) | `_should_accept_text_only_first_pass` | tras borrar las 3 anteriores el cuerpo se reduce a 4 ramas estructurales; usado SOLO en L1593 | REWRITE_SMALL (fold inline) | idem |

---

## 6. Sobreingeniería confirmada

| capa | por qué sobra | alternativa simple | acción |
|---|---|---|---|
| Backends LLM en `agent.py` | mezcla con loop de turno; ya existe `llama_backend.py` y `cloud_fallback.py` | crear `turn/backends/` con `openai_compat.py`, `null.py`, `ollama_bootstrap.py`; reexportar desde `agent.py` para no romper imports | extraer en C2 |
| `cloud_fallback.py` | ¿se usa en runtime? grep dice que no en agent.py; sólo tests | NEEDS_RUNTIME_PROOF antes de tocar; si sólo tests, mover a `tests/_helpers` | C5 |
| `UNIVERSAL_AGENT_KERNEL` siempre inyectado en prompt | duplica "POLICY" del kernel principal y siempre añade ~672 chars en texto puro | gating env `CARTER_UNIVERSAL_KERNEL_PROMPT` (default off para texto) | C4 |
| Stubs `_looks_like_*_question` post-F8 | retornan False; llamados ~6 veces por turno | borrar y simplificar | C1 |
| `_should_accept_text_only_first_pass` | una vez borradas las 3 stubs, su lógica colapsa a "no JSON, no work_units" | inline | C1 |
| Bloque GUI CAPABILITIES STATUS cuando vision_tier=NONE (~700 chars) | en una máquina con LLM_VISION configurado el bloque corto está OK; cuando no hay backend, mete texto largo en cada turno | KEEP por ahora — es informativo y único; medir en smoke | — |
| `OpenAI/Anthropic CloudBackend` paralelos | redundancia conceptual con `OpenAICompatAgentBackend` | si uso real es nulo: DELETE; si es tests, mover | C5 |

---

## 7. Plan quirúrgico de cierre total

Cada fase = un commit, pytest después de cada fase, smoke al final.

### C0 — Snapshot baseline (READ-ONLY)
- Ejecutar pytest baseline `--ignore=tests/test_main_jarvis.py` y guardar.
- Medir prompt size (`_build_system_prompt()` len).
- Medir `agent.py` LOC.
- Output: `audit/C0_baseline.json`.

### C1 — Eliminar stubs F8 muertos en agent.py
**Objetivo:** quitar las 3 funciones `_looks_like_*_question` y simplificar
`_should_accept_text_only_first_pass`.

- Archivos: `src/carter_v2/turn/agent.py`.
- Cambio:
  - borrar L576-598 (3 stubs).
  - en L599 reescribir `_should_accept_text_only_first_pass` para:
    `return reply.strip() and not reply.startswith(("{","[")) and '"work_units"' not in reply and '"tool_name"' not in reply` y, si quiere mantener pure-conv preferencia, llamar `_is_pure_conversational(user_text)`.
  - en L1223-1225 borrar las 3 condiciones `not _looks_like_*`.
  - en L1621 borrar la rama `_looks_like_personal_memory_query` (queda solo lo demás del condicional).
- Riesgo: MUY BAJO (cuerpo era constante).
- Tests: pytest completo.
- Rollback: git revert HEAD~.

### C2 — Limpiar carpeta basura `custom_types.py/`
- Archivos: `src/carter_v2/custom_types.py/` (vacía).
- Cambio: `Remove-Item -Recurse -Force`.
- Riesgo: NULO.
- Tests: pytest.
- Rollback: re-crear (vacía).

### C3 — Mover backends de agent.py a `turn/backends/`
**Objetivo:** sacar `OpenAICompatAgentBackend`, `NullAgentBackend` y la sección
de bootstrap Ollama de `agent.py`.

- Archivos nuevos:
  - `src/carter_v2/turn/backends/__init__.py` (re-export).
  - `src/carter_v2/turn/backends/openai_compat.py` ← `OpenAICompatAgentBackend`.
  - `src/carter_v2/turn/backends/null.py` ← `NullAgentBackend`.
  - `src/carter_v2/turn/backends/ollama_bootstrap.py` ← funciones `_ollama_*`,
    `_create_speculative_modelfile`, `_auto_backend`, `_tcp_probe`.
- Cambio en `agent.py`:
  - eliminar definiciones movidas.
  - re-exportar al final del módulo:
    `from .backends.openai_compat import OpenAICompatAgentBackend`
    `from .backends.null import NullAgentBackend`
    `from .backends.ollama_bootstrap import (_auto_backend, _try_start_ollama, _ollama_env_optimized, _apply_ollama_env_locally, _ollama_best_model, _ollama_best_draft, _ollama_available_models, _create_speculative_modelfile, _tcp_probe)`
  - mantener compat con `patch("carter_v2.turn.agent._auto_backend")` y similares.
- Riesgo: MEDIO (muchos imports y patch sites en tests).
- Tests: pytest completo + grep `patch("carter_v2.turn.agent.` para verificar.
- Rollback: git revert.

### C4 — Gate `UNIVERSAL_AGENT_KERNEL` en prompt
- Archivos: `src/carter_v2/turn/_system_prompt.py`,
  `src/carter_v2/universal/context.py`.
- Cambio: nuevo env `CARTER_UNIVERSAL_KERNEL_PROMPT` (default OFF). Si OFF,
  `_build_system_prompt` no incluye `universal_block`.
- Riesgo: BAJO.
- Tests: ajustar `test_carter_v2.py` o asserts que cuenten kernel; ejecutar pytest.
- Rollback: env por default ON.

### C5 — Verificar `cloud_fallback.py`
- Sub-fase 5a: grep + import audit. Si ningún test ni runtime lo usa → DELETE
  archivo + tests asociados. Si lo usa sólo `tests/`, mover a `tests/_helpers`.
- Si lo usa runtime → KEEP y documentar.
- Riesgo: BAJO (con grep previo).

### C6 — Verificar `intent_resolution.py`
- Sub-fase 6a: NEEDS_RUNTIME_PROOF — grep, decidir KEEP o REMOVE.

### C7 — Smoke runtime
- Si Qwen disponible → ejecutar `audit/smoke_runner_fsmoke.py` o `run_carter_gpu.ps1`
  con los 14 prompts del enunciado y registrar.

### C8 — Reporte final
- `FINAL_TEXT_CLOSURE_REPORT.md` con métricas antes/después.

---

## 8. Qué NO tocar

- **`AgentEngine.run` (~778 líneas).** Tocar el orden interno requeriría tests
  de integración Qwen reales, no sólo unit. Riesgo de regresión alto y la
  arquitectura ya quedó razonable; la deuda se documenta.
- **`adapters/tools.py` (2234 LOC).** Es lista de ToolDefinition; partirlo es
  útil pero no urgente y puede romper imports. Dejado para próximo ciclo.
- **`gui_agent.py` (1217 LOC) y `web.py` (1086 LOC).** Capabilities grandes,
  pero coherentes y con test coverage propio. No es deuda crítica de texto.
- **`session/skills.py` (791 LOC) + `embeddings.py`.** Sistema de skills es
  experimental pero gated; activarlo no afecta el path de texto puro.
- **`interfaces/`.** Off-by-default; tocar levantaría riesgo sin beneficio.
- **`steam.py`, `power.py`.** Gated por policy; off en texto puro.
- **`MEMORY.md` y `.carter/memory.db`.** Backup antes de cualquier cambio
  destructivo de memoria (no hay cambios planeados en este ciclo).

---

## 9. Smoke final requerido

### Pytest gate (post-cada-fase)
```
cd Carter_v2
pytest -q --ignore=tests/test_main_jarvis.py
```

### Smoke Qwen real (final, sólo C7)
```
$env:CARTER_TIMING="1"
$env:CARTER_AUTO_APPROVE_HIGH="1"
.\run_carter_gpu.ps1
```

Prompts:
1. hola
2. quien eres
3. who are you
4. quiero saber quien es batman
5. who is Batman
6. que hora es
7. what time is it
8. cuál es mi IP
9. qué herramienta usaste?
10. recuerda que mi proyecto se llama Carter
11. qué recuerdas de mí
12. abre Notepad y luego ciérralo
13. abre Opera y busca Batman
14. abre Steam, ve a biblioteca y luego cierra Steam

Métricas por turno:
- respuesta (1 línea)
- total_ms, llm_calls, tool_count, tools_exposed, tools_called
- retry_reason (si hay)
- used_vision, used_universal_runner, memory_changed
- pass/fail (criterio honesto, no cosmético).

Si Qwen/Ollama no están disponibles localmente al cierre, se documenta como
"smoke pendiente — requiere host con Ollama" y se mantiene `audit/F-SMOKE_smoke.json`
del ciclo anterior como baseline.
