# 01 — Auditoría Arquitectura

**Fecha**: 2026-05-11
**Insumos**: lectura completa de `agent.py` (1397 LOC), `step_planner.py`, `planner.py`, `mission_detector.py`, `turn_profile.py`, `models/gemma4.py`, `prompt.py`, `verify.py`, `verifier_orchestrator.py`, `tool_retrieval.py`, `tools/*`, bench oficial 54 P0 (41/54 PASS = 75.93%).

---

## 1. Diagrama actual (lo que existe en el código)

```
USER INPUT
   │
   ▼
┌──────────────────────────────────────────────────────┐
│ run_turn(user_text)  — agent.py:274                  │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ Pre-LLM determinismo (4 routers en serie)   │   │
│  │                                              │   │
│  │  1. detect_mission()    [mission_detector]   │   │
│  │  2. plan_mission(LLM)   [planner.py LLM CALL]│   │
│  │  3. plan_turn()         [step_planner]       │   │
│  │     ├─ detect_archetype                      │   │
│  │     ├─ pre_llm_short_circuit                 │   │
│  │     ├─ forced_tool_call (VIOLA V7)           │   │
│  │     └─ suppress_tools                        │   │
│  │  4. select_profile()    [turn_profile/gemma4]│   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ Build context                                │   │
│  │  - tool_retriever.select(top-K)              │   │
│  │  - build_system_message (CORE 3400 tokens)   │   │
│  │  - recent_history                            │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ LLM CALL #1 (Gemma 4 4B :8080)               │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ Post-LLM heurísticas (agent.py 462-575)      │   │
│  │  - _looks_like_surrender                     │   │
│  │  - emitted_tool_as_text regex                │   │
│  │  - canned_trivial detector                   │   │
│  │  - retry-with-nudge                          │   │
│  │  - strip_planning_leakage                    │   │
│  │  - fix_carter_vocative                       │   │
│  │  - rewrite_claim_to_unverified               │   │
│  │  - no_action_footer                          │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ [Si tool_calls] Execute loop                 │   │
│  │  _execute_tool_calls -> _chain_more_tools    │   │
│  │  depth<=8, budget<=120s                      │   │
│  │   - safety.evaluate_tool_call                │   │
│  │   - tools.dispatch                           │   │
│  │   - verify.verify (por-tool)                 │   │
│  │   - _compute_post_action_steps (auto)        │   │
│  │   - loop_state.record + detect_stuck         │   │
│  │   - LLM CALL #N+1 (follow-up con result)     │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ _finalize_turn(...)                          │   │
│  │   verifier_orchestrator.compute_outcome      │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
└──────────────────────────────────────────────────────┘
   │
   ▼
TurnResult(reply, tool_calls, outcomes, outcome)
```

---

## 2. Problemas estructurales identificados

### P1: Tres routers compitiendo por decidir lo mismo

| Router | Función | Lo que decide |
|--------|---------|---------------|
| `mission_detector.detect_mission()` | `mission_detector.py:120` | `is_mission: bool` por scoring de separadores + imperativos |
| `planner.plan()` | `planner.py:74` | `Plan` con steps (HACE UN LLM CALL EXTRA) |
| `step_planner.plan_turn()` | `step_planner.py:433` | `TurnPlan(archetype, depth, budget, k, forced_tool_call)` |

**Síntoma**: para "abre Spotify y baja volumen a 20":
- `detect_mission` → `is_mission=True` (n_separators≥2 + imperativos≥2)
- `plan_mission` → llama LLM con `PLANNER_SYSTEM` para devolver stubs → **500-800ms extra**
- `plan_turn` → archetype="MISSION", depth=8, budget=30000ms

Tres routers, tres respuestas, redundancia clara. Y el plan que devuelve `plan_mission` se inyecta al system_msg como texto adicional, **bloating el prompt** que va al LLM principal.

### P2: Per-app hardcodes en step_planner (viola V7)

`step_planner.py:320-361` contiene:

```python
_WEB_APP_URLS = {"youtube": "https://...", "github": "...", "gmail": "...", ...}  # 18 entries
_DEEPLINK_APPS = {"spotify": (...), "steam": (...), "discord": (...), ...}        # 7 entries
_NATIVE_APPS = {"notepad", "calculadora", "explorador", "paint", ...}             # 20 entries
```

`_detect_forced_tool_call()` matchea estas listas y emite un tool_call **antes de la primera LLM call**. Esto:
- Es lo que hace que C16-01 "abre stean" pase en 14s (sin LLM call) vs los 21s normales.
- Viola el Valor 7 explícitamente declarado en ContextoCarter.md: *"Carter no debe tener hacks por app"*.
- Reduce el rol del LLM a "puerta secundaria" para los casos comunes.

**Decisión**: Anthropic dice "keep loop minimal, rely on model's native capabilities" pero también dice "It's therefore crucial to design toolsets and their documentation clearly and thoughtfully." Resolver determinísticamente NO es malo per se. El problema es que esto está en `step_planner.py` (router con literal lists), no en una capa declarativa documentada.

### P3: agent.py monolítico (1397 LOC)

23 métodos en una clase, mezclando:
- Construcción de contexto
- Decisiones de routing
- Heurísticas post-LLM
- Ejecución de tools
- Verificación
- Streaming
- History management

**Anthropic dice**: "frameworks can create extra layers of abstraction that obscure underlying prompts and responses". Pero también: "find the simplest solution possible". 1397 LOC en una clase no es simple.

### P4: Verifier por-tool, no por-misión

`verify.py` registra verifiers 1:1 con tool name. `verifier_orchestrator.py` agrega un outcome global por **conteo de True/False/None**.

**Lo que falta**: un verifier que tome la **misión original** + **resultados acumulados** y diga si la intención quedó cumplida.

Ejemplo: prompt "crea carpeta sandbox/test, crea archivo nota.txt, escribe hola, ábrelo".
- Tool 1: `filesystem_create_dir("sandbox/test")` → confirmed=True
- Tool 2: `filesystem_write("sandbox/test/nota.txt", "hola")` → confirmed=True
- Tool 3: `filesystem_open("sandbox/test/nota.txt")` → confirmed=None (dispatched, app abrió)

Verifier por-tool: 2 True + 1 None → orchestrator dice **PARTIAL** (porque hay None).
Verifier por-misión: la intención completa se cumplió. Output esperado: **DONE**.

CLAUDE.md roadmap dice esto explícitamente: *"Verifier rewrite: pasar de 'tool ok = PASS' a 'intent fulfilled = PASS'"*. Sigue pendiente.

### P5: Post-LLM rewriting puede ocultar bugs reales

`agent.py:566-571`:
```python
raw = verify.strip_planning_leakage(resp.text.strip()) or "(sin respuesta)"
raw = verify.fix_carter_vocative(raw)
rewritten = verify.rewrite_claim_to_unverified(raw, [], [])
reply = rewritten + verify.no_action_footer(rewritten, 0)
```

4 capas de string-rewriting sobre el reply del LLM. Si el modelo dice algo correcto pero raro, el rewriter puede romperlo. Si el modelo miente, el rewriter trata de detectarlo por substrings ("listo", "abierto") — pero **los falsos positivos son problema**.

Test fallido `test_rewrite_triggers_for_short_action_claim`: el código actual dice "No llegué a ejecutar nada en este turno" en vez del string esperado por el test "No ejecuté ninguna acción". El rewriter cambia de forma sin avisar; los tests no se mantienen.

### P6: Latencia per-tool (medida con bench oficial)

Datos del bench 54 P0:
- **0 tools**: avg 3.9s, max 11.8s
- **1 tool**: avg **16s** (target 12s para tool simple — 33% sobre)
- **2 tools**: avg **42s** (target 20s — 110% sobre)
- **4+ tools**: 73s (C14-01)

Causa: cada tool dispatch hace LLM follow-up call para que el modelo "vea" el resultado. Con Gemma 4 4B + tools=top-K, cada follow-up es 6-12s.

**Esto es lo que rompe budgets**. No es funcional, es estructural: el agent loop hace UN llamado de LLM por tool. 4 tools = 5 LLM calls = 30-50s.

UI-TARS-2 reporta: "agents take 1.4-2.7x more steps than necessary, each successive step 3x longer". Carter cae exactamente en ese patrón.

### P7: Falta abstracción de capabilities por modelo

`adapters/llamacpp.py` tiene parches específicos para Gemma 4 quirks:
- `chat_template_kwargs: {"enable_thinking": False}` (Gemma 4 pone JSON en reasoning)
- Retry on finish_reason="length" + tool_call truncated
- Filtrado del reasoning field cuando content=""

Esto no es per-se malo. **Pero el agent.py no sabe nada de esto.** Si mañana cambia a Qwen3-VL-7B, no hay forma declarativa de decir "Qwen3 no necesita este parche". Acoplamiento implícito.

### P8: Skills, skill_store, planner, step_planner — overlap conceptual

Carter tiene 4 mecanismos para "decir qué hacer":
- `skills.py`: registry estilo Anthropic Agent Skills (playbooks curados)
- `skill_store.py`: skill record con LLM-critic (acumula recipes)
- `planner.py`: plan stubs con LLM (alto nivel)
- `step_planner.py`: forced_tool_call con per-app lists

No hay jerarquía clara: ¿cuál gana si todos están activos?

---

## 3. Arquitectura propuesta (10/10)

### 3.1 Principios

1. **Single source of truth para routing**: un solo router pre-LLM.
2. **Separation of concerns rigurosa**: agent.py < 600 LOC, sólo el while-loop principal.
3. **Verifier por-misión declarativo**: estado de misión = first-class citizen.
4. **Layer de capabilities por modelo**: parches específicos en `models/<name>.py`, agent.py agnóstico.
5. **Per-app data declarativa**: registry HKCR + UWP Get-StartApps, NO listas hardcoded en código.
6. **Latencia por-misión presupuestada**: en vez de "depth<=8 budget<=120s", presupuesto declarativo por arquetipo.

### 3.2 Estructura objetivo

```
carter_v4/
├── core/
│   ├── agent.py              # while loop, <500 LOC
│   ├── turn_state.py         # MissionGoal, OutcomeState (Pydantic)
│   ├── router.py             # UN SOLO router pre-LLM
│   └── prompt_loader.py      # carga CORE_PROMPT por modelo
│
├── models/
│   ├── base.py               # ModelCapability dataclass + protocol
│   ├── gemma4.py             # capabilities + prompt + sampling
│   └── qwen3.py              # idem
│
├── tools/
│   ├── _base.py              # @tool decorator + schema spec
│   ├── registry.py           # get_catalog, get_spec, dispatch
│   ├── apps.py               # universal app resolver (sin listas)
│   ├── gui.py                # screenshot, click, type, focus
│   ├── filesystem.py         # read, write, list, create
│   ├── web.py                # open_url, search, fetch
│   ├── system.py             # volume, time, battery
│   └── deeplink.py           # universal HKCR-based
│
├── verify/
│   ├── per_tool.py           # register_verifier(tool) — existing
│   ├── mission_goal.py       # NUEVO: verifica intent del user
│   └── orchestrator.py       # agrega outcomes
│
├── retrieval/
│   ├── tool_retriever.py     # RAG-MCP top-K
│   └── memory.py             # SQLite memory
│
├── safety/
│   ├── intent_detector.py    # destructive_intent multilingual
│   └── policy.py             # evaluate_tool_call + confirmation
│
├── loop/
│   ├── detector.py           # loop_detection v2 — existing
│   └── recovery.py           # causal-focus + nudge
│
└── observability/
    ├── tracing.py            # per-turn trace (jsonl)
    └── streaming.py          # progress callbacks
```

### 3.3 Flujo objetivo

```
USER INPUT
   │
   ▼
┌──────────────────────────────────────────────────────┐
│ run_turn(user_text)                                  │
│                                                      │
│  1. Router único: classify(user_text) → Intent       │
│     - archetype: TRIVIAL/KNOWLEDGE/TOOL/MISSION      │
│     - mission_goal: text + expected_states           │
│     - sampling profile                               │
│                                                      │
│  2. Build minimal context                            │
│     - CORE_PROMPT (<1500 tokens)                     │
│     - tools = retriever.select(top-K segun archetype)│
│     - memory facts (top-5)                           │
│                                                      │
│  3. LLM call (1 vez)                                 │
│                                                      │
│  4. Execute & verify por-tool                        │
│     loop until: no more tool_calls OR budget         │
│       - dispatch + verify                            │
│       - mission_goal.update_state(tool, outcome)     │
│       - if mission_goal.fulfilled: break             │
│                                                      │
│  5. Mission-level outcome                            │
│     - DONE | PARTIAL | UNVERIFIED | FAILED | NEEDS_USER│
│                                                      │
│  6. Reply assembly                                   │
│     - LLM final summary OR rewriter                  │
└──────────────────────────────────────────────────────┘
```

### 3.4 Decisiones clave

| Decisión | Justificación | Fuente |
|----------|--------------|--------|
| Router único (colapsar 3→1) | "keep loop minimal" + reducir LLM overhead | [Anthropic Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) |
| CORE_PROMPT <1500 tokens | "Large system prompts with 22+ tools result in accuracy degradation" + Claude Code reference | [HuggingFace Gemma discussion](https://huggingface.co/google/gemma-3-27b-it/discussions/24) |
| top-K=8 default, 16 en MISSION | RAG-MCP demuestra +30 pts accuracy + -50% tokens | [arxiv 2505.03275](https://arxiv.org/abs/2505.03275) |
| Mission-goal verifier | Voyager: verifier verifica el OBJETIVO, no tool atómica | [Voyager NeurIPS 2023](https://voyager.minedojo.org/) |
| ModelCapability protocol | Decouple agent de quirks de backend específico | [Pydantic AI docs](https://ai.pydantic.dev/agent/) — provider switching |
| Per-app via registry HKCR + Get-StartApps | Universal cross-locale, sin listas hardcoded | [Microsoft Learn](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85)) |
| Vision inline en MISSION turn | UI-TARS-2: percepción integrada al action token | [arxiv 2509.02544](https://arxiv.org/abs/2509.02544) |

---

## 4. Trade-offs honestos

### Trade-off 1: Eliminar `forced_tool_call` (per-app lists)

**Pro**: V7 cumplido (sin per-app hardcodes).
**Contra**: para "abre stean", el LLM tiene que resolver `gui_deeplink(steam, library)`. Latencia: +6-10s. **Va a romper budget de C16**.

**Mitigación propuesta**:
- Sacar las listas de step_planner.
- Pero mantener un **dispatcher universal** que mapee "abre X" → resolve_app(X) → si registered deeplink → gui_deeplink, else app_open.
- Esto SÍ es V7-compliant porque resolve_app es universal (Get-StartApps + procesos + lnk).

### Trade-off 2: Mission goal verifier requiere LLM call extra

**Pro**: V3 reforzado (honestidad por-misión).
**Contra**: +1 LLM call (~3-6s) al final de cada misión.

**Mitigación propuesta**:
- Solo en MISSION archetype (no en TOOL_SIMPLE).
- Estructural sin LLM cuando posible: "n_imperativos del prompt == n_outcomes confirmed".
- LLM solo cuando hay ambigüedad.

### Trade-off 3: Refactor agent.py rompe historial git/blame

**Pro**: legibilidad + testability.
**Contra**: PR grande, riesgo de regresión.

**Mitigación**:
- Cambios pequeños y verificables (V24).
- Test de integración antes y después.
- No mezclar refactor con cambio funcional.

### Trade-off 4: Eliminar `plan_mission` (LLM call extra)

**Pro**: -500-800ms por misión.
**Contra**: el plan inyectado guiaba al LLM principal en misiones complejas. Riesgo: misiones largas pierden estructura.

**Mitigación propuesta**:
- Si el archetype es MISSION_LONG (>4 pasos), mantener plan_mission.
- Para MISSION normal (2-4 pasos), Gemma 4 puede hacerlo solo con buena descripción de tools.

---

## 5. Criterios de éxito para 10/10 arquitectura

Solo declaro 10/10 cuando:

- [ ] agent.py < 600 LOC y se entiende sin leer otros módulos.
- [ ] **Un solo router** decide archetype + sampling + mission_goal.
- [ ] **Cero per-app hardcodes** (búsqueda probada con grep).
- [ ] **Mission goal verifier** implementado, testeado, usado por orchestrator.
- [ ] **ModelCapability protocol** para que agent.py no conozca quirks de Gemma 4 directamente.
- [ ] **Tests de integración** que ejecuten `Agent.run_turn(...)` con mock LLM, golden paths.
- [ ] **GUI tiers ordenados**: deeplink > URI > UIA > vision, declarado en código.
- [ ] **Bench oficial 540 corrido** con score documentado (esperado: ≥85% en P0).
- [ ] **Decisión escrita en este informe** para cada componente, con fuente externa.

Score actual: **7.5/10**. Distancia a 10: 4 issues estructurales (P1, P3, P4, P7).
