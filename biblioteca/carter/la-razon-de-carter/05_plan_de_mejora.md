# 05 — Plan de Mejora Priorizado

**Fecha**: 2026-05-11

Objetivo: subir Carter v4 de **7.5 / 6 / 5** (diseño / impl / Gemma) a **10 / 10 / 10** con evidencia defendible.

---

## P0 — Cambios estructurales (semana 1)

### P0-1: Unificar 3 routers en 1

**Problema**: `mission_detector` + `planner.plan` + `step_planner.plan_turn` deciden lo mismo en serie.

**Acción**:
1. Crear `core/router.py` con `Intent` dataclass único: `archetype, sampling_profile, mission_goal, retrieval_k, forced_action`.
2. Migrar lógica útil de `mission_detector` (scoring estructural) a `router._is_mission`.
3. Eliminar `plan_mission()` LLM-call extra. Reemplazar por `MissionGoal.from_text(user_text)` estructural.
4. Mantener `step_planner.detect_archetype` como módulo interno del router.
5. **Eliminar** `step_planner._WEB_APP_URLS`, `_DEEPLINK_APPS`, `_NATIVE_APPS`. Reemplazar por universal `apps.resolve_app + deeplinks.is_protocol_registered`.

**Tests**: golden paths para cada archetype.
**Métrica éxito**: `agent.run_turn` invoca un solo router; `grep "select_profile\|detect_archetype\|plan_turn\|detect_mission\|plan_mission"` ≤ 1 resultado.
**Evidencia externa**: Anthropic "keep loop minimal", V7 ContextoCarter.

### P0-2: CORE_PROMPT <1500 tokens

**Problema**: 3,400 tokens actuales (medido `wc -c prompts/gemma4_e4b_prompt.py` ÷ 4).

**Acción**:
1. Recortar a frases declarativas cortas.
2. Mover ejemplos largos a recuperación condicional por archetype.
3. **Añadir frase doc-recomendada**: *"Only call a tool when the user asks for an action. For questions and explanations, respond in plain text."*

**Tests**: medir tokens con tiktoken-equivalente; smoke a 10 casos comparativos.
**Métrica éxito**: <1500 tokens, sin degradar PASS rate en bench P0.
**Evidencia externa**: HF Gemma discussion #24, Anthropic.

### P0-3: Tools visibles ≤16 default

**Problema**: anchors=14 + top-K=12 = 26. Anaphora boost = 14+20 = 34.

**Acción**:
1. Reducir anchors a 6-8 (los TRULY transversales: memory, app_open, gui_screenshot, terminal_run, web_search).
2. top-K default = 8.
3. MISSION archetype: top-K = 12.
4. Eliminar anchors innecesarios (vision_check_blockers, system_get_volume — el retriever los matchea cuando hace falta).

**Tests**: medir tools count en cada archetype.
**Métrica éxito**: ≤16 default, ≤20 MISSION.
**Evidencia externa**: HF Gemma discussion #24 ("5-15 tools recomendado").

### P0-4: Mission goal verifier

**Problema**: verifier por-tool no sabe si la **intención** del user quedó cumplida.

**Acción**:
1. Crear `verify/mission_goal.py`:
   ```python
   @dataclass
   class MissionGoal:
       text: str  # prompt original
       expected_outcomes: list[ExpectedOutcome]  # heuristica estructural
       current_state: dict
       def is_fulfilled(self, outcomes) -> bool
       def progress_summary(self) -> str
   ```
2. Estructural sin LLM:
   - Si prompt tiene N imperativos y se ejecutaron N tools con `confirmed!=False`, → fulfilled.
   - Si prompt tiene "abre X y haz Y", expected = [app_open_or_deeplink, action_tool].
3. Integrar en `verifier_orchestrator.compute_outcome`:
   - Si mission_goal.is_fulfilled → outcome = `COMPLETED`.
   - Si parcial → `PARTIAL` con detalle de qué falta.
   - Si ningún imperativo ejecutado → `INTENT_NOT_FULFILLED`.

**Tests**: golden cases del bench: C14-04 chain perfecta → COMPLETED. C14-01 Steam Batman parcial → PARTIAL con "no encontró Batman".
**Métrica éxito**: bench P0 sube ≥3 pts por mejor outcome reporting.
**Evidencia externa**: Voyager NeurIPS 2023.

### P0-5: Refactor agent.py < 600 LOC

**Acción**: extraer módulos:
- `core/context_builder.py` (build_system_message wiring)
- `core/execution.py` (`_execute_tool_calls` + `_chain_more_tools`)
- `core/reply_processor.py` (heurísticas post-LLM)
- `core/history.py` (compact + recent)
- `core/nudge.py` (`_post_tool_continuation_nudge`, `_continuation_nudge`)

`agent.py` queda con:
- `__init__` (300 LOC máx)
- `run_turn` (200 LOC máx) — el while loop principal
- `reset/close` (50 LOC)

**Tests**: integration test con mock LLM, golden paths.
**Métrica éxito**: agent.py < 600 LOC; tests pasan.
**Evidencia externa**: Anthropic "keep loop minimal".

---

## P1 — Optimización Gemma 4 4B (semana 2)

### P1-1: Reducir LLM calls post-tool

**Problema**: cada tool dispatch → 1 LLM follow-up (~6-10s).

**Acción**:
1. Si `mission_goal.is_fulfilled` después de un tool, **NO hacer follow-up**. Generar reply directamente.
2. Si `verifier.confirmed=True` Y hay más tools planeados (MissionGoal.expected_outcomes restantes), **encadenar** sin follow-up extra (proximate next tool por heuristica del archetype).
3. Follow-up SOLO cuando: hay ambigüedad (verifier=None+expected verify) O tool=FAIL O mission_goal incompleta + no hay próxima acción obvia.

**Tests**: medir LLM calls por bench case; meta -30%.
**Métrica éxito**: latencia 1-tool ≤12s avg (vs 16s actual); 2-tool ≤25s (vs 42s).
**Evidencia externa**: MLSys WukLab OSWorld-Human ("each step 3x longer").

### P1-2: Vision inline en archetype MISSION/TOOL_GUI

**Problema**: `vision_describe_dialog` es tool que el LLM debe pedir. En misión GUI, debería ser automático.

**Acción**:
1. Generalizar `CARTER_V4_AUTO_VISION_DESCRIBE`: en archetype con tool GUI emitida, post-dispatch inyecta `[contexto visual: <descripción>]` al next_messages.
2. Solo si Gemma 4 multimodal está disponible (`mmproj` cargado).
3. Cap latencia: si vision_describe>5s, skip y dejar al modelo seguir sin.

**Tests**: C13-02 "click si visible" con vision inline.
**Métrica éxito**: misiones GUI suben PASS rate.
**Evidencia externa**: UI-TARS-2 percepción integrada.

### P1-3: Eager-load embedder

**Problema**: cold start 21s primera "hola".

**Acción**:
1. En `Agent.__init__`, llamar `_tool_retriever.embed_catalog()` síncronamente.
2. Llamar `memory._get_embedder()` síncronamente.
3. Resultado: pagar 2-3s una vez en boot, no recurrentes.

**Tests**: smoke "hola" primera vez post-init.
**Métrica éxito**: cold start "hola" <8s.
**Evidencia externa**: V2 ContextoCarter (latency target).

### P1-4: ModelCapability protocol

**Problema**: agent.py acoplado a quirks de Gemma 4 (thinking field, etc.).

**Acción**:
1. Crear `models/base.py`:
   ```python
   @dataclass
   class ModelCapability:
       name: str
       emits_thinking: bool          # True → adapter filtra reasoning field
       supports_jinja_tools: bool    # True → tool_calls OpenAI-compat
       max_tools_visible: int        # 16 para 4B, 30 para 7B+
       sampling_defaults: dict
       system_prompt_path: str
       requires_alt_press_focus: bool  # Windows-specific
   ```
2. `models/gemma4.py` exporta `GEMMA4_4B = ModelCapability(...)`.
3. `agent.py` consulta `self.model_cap` en vez de hardcodear paths.

**Tests**: switch entre Gemma y Qwen sin tocar agent.py.
**Métrica éxito**: agent.py no menciona "gemma" ni "qwen".
**Evidencia externa**: Pydantic AI provider abstraction.

---

## P2 — Tests y observabilidad (semana 3)

### P2-1: Tests del agent loop con mock LLM

**Acción**:
1. Crear `tests/test_agent_integration.py`.
2. Mock LLM que devuelve scripts pre-definidos.
3. Golden paths:
   - "hola" → no tools, reply <100 chars.
   - "abre Notepad" → app_open + verifier confirmed.
   - "borra mi carpeta Documentos" → pending_confirm.
   - "crea X, escribe Y, ábrelo" → 3 tools encadenados.

**Métrica éxito**: ≥20 integration tests, ≥80% del flujo principal cubierto.

### P2-2: Tracing jsonl per turn

**Acción**:
1. Crear `observability/tracing.py`.
2. Por turn: write `{ts, trace_id, user_text, archetype, tools, verifiers, outcome, latency_ms}` a `~/.carter_v4/traces.jsonl`.
3. Rotar diariamente.

**Métrica éxito**: cada turn produce un trace; útil para debugging post-mortem.

### P2-3: Arreglar 4 tests fallando

**Acción**: actualizar strings en `tests/test_verify.py` para match al output actual.

**Métrica éxito**: 144/144 passing.

---

## P3 — Polish (después)

### P3-1: Pydantic schemas para MissionGoal, OutcomeState, ToolResult

### P3-2: Error_kind normalizado en todas las tools

### P3-3: Curriculum generator (Voyager componente 1) — nice to have

### P3-4: Online-Optimized RAG retriever — nice to have

---

## Métricas globales de éxito

| Métrica | Baseline | Target 10/10 |
|---------|----------|--------------|
| agent.py LOC | 1,397 | <600 |
| CORE_PROMPT tokens | ~3,400 | <1,500 |
| Tools visibles default | 26 | ≤16 |
| Bench P0 PASS rate | 75.93% | ≥85% |
| Latencia 1-tool avg | 16.0s | ≤12s |
| Latencia 2-tool avg | 42.3s | ≤25s |
| Cold start "hola" | 21s | <8s |
| Tests pass | 140/144 | 144/144 + 20 integration |
| Per-app hardcodes | 3 listas (45 entries) | 0 |
| LLM calls promedio per turn | ~N+1 | ≤(N/2)+1 |

---

## Riesgos del plan

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Refactor agent.py rompe tests | Alta | Tests integration ANTES del refactor |
| Eliminar `forced_tool_call` sube latencia | Alta | Universal "open" handler reemplaza |
| Mission goal verifier mide mal | Media | Validar contra bench 540 antes de merge |
| CORE_PROMPT corto baja accuracy | Media | A/B test con bench P0 |
| Cambio de top-K rompe casos previos | Baja | Anchors críticos preservados |

---

## Cronograma (orientativo)

- **Día 1**: P0-1 (router único) + tests integration mínimos
- **Día 2**: P0-2 (CORE_PROMPT) + P0-3 (tools≤16)
- **Día 3**: P0-4 (mission goal verifier)
- **Día 4**: P0-5 (refactor agent.py)
- **Día 5**: P1-1 (reducir LLM calls)
- **Día 6**: P1-2 (vision inline) + P1-3 (eager load) + P1-4 (ModelCapability)
- **Día 7**: P2 (tests + tracing + 4 fixes)
- **Día 8**: Bench oficial 540 completo + análisis
- **Día 9**: Fixes post-bench
- **Día 10**: Bench final + informe 07 con score defendible

---

## Criterios para declarar fin de plan

Solo termino cuando puedo defender:

1. **Diseño 10/10**: agent.py refactorizado, 1 router, mission goal verifier, ModelCapability, sin per-app hardcodes.
2. **Implementación 10/10**: tests 144+20 pass, tracing jsonl, error_kind, Pydantic schemas, <600 LOC en agent.py.
3. **Match Gemma 4 4B 10/10**: CORE_PROMPT <1500, tools≤16, frase doc-recomendada incluida, latencia 1-tool ≤12s, bench P0 ≥85%.

Si cualquiera de los 3 no llega, declaro el score honesto y explico por qué.
