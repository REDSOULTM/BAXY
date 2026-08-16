# 02 — Auditoría Implementación

**Fecha**: 2026-05-11
**Insumos**: code review de los top-10 archivos por LOC, ejecución de tests, bench 54 P0.

---

## 1. Métricas medidas

| Métrica | Valor | Target | Gap |
|---------|-------|--------|-----|
| LOC totales | 15,251 | sin target específico | — |
| Archivos .py | 56 | sin target | — |
| agent.py LOC | **1,397** | <400 (autor) / <600 (mi recomendación) | **2.3-3.5x** |
| Tools registradas | 61 | <22 visible (Google docs) | top-K mitiga |
| CORE_PROMPT chars | 13,580 (~3,400 tokens) | <1,500 tokens | **2.3x** |
| Tests pass | 140/144 | 144 | 4 fails (encoding) |
| Bench P0 PASS rate | 41/54 (75.93%) | ≥85% | **9 pts gap** |
| Latencia 1-tool avg | 16s | 8-12s | **33-100% sobre** |
| Latencia 2-tool avg | 42s | 20s | **110% sobre** |
| Cold start "hola" | 21s (sesión anterior) | <5s | **4x sobre** |

---

## 2. Archivos problemáticos

### 2.1 `agent.py` (1,397 LOC) — God object

23 métodos privados, 5 funciones top-level, 1 clase `Agent`.

**Inventario de responsabilidades** (mezcladas en la misma clase):

| Responsabilidad | Línea aprox | Debería estar en |
|----------------|-------------|------------------|
| Construcción de context (system_msg + history) | 324-345 | `core/context_builder.py` |
| Routing pre-LLM (call mission_detector + planner + step_planner) | 301-407 | `core/router.py` (unificado) |
| LLM call wiring | 437-460 | `core/llm_executor.py` |
| Post-LLM heuristics (surrender, tool-as-text, canned) | 462-565 | `core/reply_processor.py` |
| Tool execution loop | 636-885 | `core/execution.py` |
| Chain loop (recursive) | 887-1100 | `core/execution.py` |
| Loop detection wiring | inline | OK pero verboso |
| Verifier orchestration | _finalize_turn | `verify/orchestrator.py` (mover wiring) |
| History compaction | 1333-1360 | `core/history.py` |
| Continuation nudge logic | 1133-1200 | `core/nudge.py` |

**Diagnóstico**: violación clara del Single Responsibility Principle. Refactor en 8 módulos < 200 LOC cada uno.

### 2.2 `tools/apps.py` (1,224 LOC)

Universal app resolver con 5 estrategias: procesos, Get-StartApps, Steam library, Start Menu lnk, PATH, web_guess. Es razonable que sea grande porque hay mucha lógica de resolución.

**Pero**:
- `_guess_web_url` puede crear daño (calculator.com). Ya corregido con SequenceMatcher 0.75.
- Scoring _score_app es compleja, fácil de quebrarse con un edge case.
- `_enumerate_start_apps` ejecuta PowerShell cada vez (cacheable).

**Recomendación**: refactor en `apps/resolver.py` + `apps/scoring.py` + `apps/cache.py`.

### 2.3 `tools/gui.py` (1,150 LOC) + `tools/gui_universal.py` (754 LOC) = 1,904 LOC GUI

Mezcla:
- Frame-diff verifier
- Window state snapshot (Win32 + UIA)
- Causal focus helpers (recién agregado)
- gui_screenshot, gui_type, gui_click, gui_keypress, gui_universal_action
- Vision_locate cache
- 5 tiers (deeplink cache, UIA, OCR, VLM)

**Diagnóstico**: legible pero acumulando responsabilidades. Refactor en:
- `gui/screenshot.py`
- `gui/actions.py` (click, type, keypress)
- `gui/window_state.py` (snapshot, focus)
- `gui/tiers.py` (UIA, OCR, VLM)

### 2.4 `step_planner.py` (481 LOC)

**Problema principal**: contiene per-app lists (`_WEB_APP_URLS`, `_DEEPLINK_APPS`, `_NATIVE_APPS`) que **violan V7**.

Resto del archivo:
- `_PROFILES` archetype → (depth, budget): razonable.
- `detect_archetype()`: razonable, estructural.
- `_detect_anaphora`: razonable.
- `_detect_forced_tool_call`: viola V7.

**Recomendación**: extraer per-app lists a registry, dejar solo el routing estructural.

### 2.5 `verifier_orchestrator.py` (390 LOC)

**9 estados** declarados (`COMPLETED`, `PARTIAL`, `FAILED`, `UNVERIFIED`, `NEEDS_USER`, `NEEDS_PERMISSION`, `BLOCKED_BY_POLICY`, `TOOL_OK_VERIFIER_INCONCLUSIVE`, `INTENT_NOT_FULFILLED`).

**Pro**: rico, explícito.
**Contra**: el agente final aún hace lógica de "summary text" que depende de strings ("despachada", "uri", "asincrónico").

`_DISPATCH_KEYWORDS` línea 75-80: strings hardcoded para detectar deeplink dispatch. Eso es frágil.

**Recomendación**: marcar `confirmable=False` en la tool_spec del verifier, no detectar por substring.

### 2.6 Duplicación de funciones críticas

| Nombre | Ubicaciones | Acción |
|--------|------------|--------|
| `select_profile` | turn_profile.py, models/gemma4.py, profiles.py | Renombrar y unificar |
| `detect_destructive_intent` | turn_profile.py, step_planner.py (`_is_destructive`) | Una fuente única |
| `_canonical_steps_for` | step_planner.py | OK, único |
| App matching | apps.py, step_planner.py (`_NATIVE_APPS`) | Solo en apps.py |

---

## 3. Calidad de código

### 3.1 Tipado

**Bueno**:
- Dataclasses usadas extensivamente (`VerifierOutcome`, `TurnPlan`, `TurnOutcome`, `Plan`).
- Type hints en signaturas.

**Mejorable**:
- `dict[str, Any]` everywhere (los args de tools, los results). Hay schema JSON pero no se valida contra Pydantic models.
- `LLMResponse.tool_calls` es `list[ToolCall]` pero `ToolCall.arguments` es `dict` sin tipo.
- No hay `Protocol` o `ABC` para `LLMAdapter` — son duck-typed.

**Recomendación**: introducir Pydantic models para `MissionGoal`, `OutcomeState`, `ToolResult`. Mantener `dict` para flexibilidad de tools, pero validar al boundary.

### 3.2 Logging

`_debug_log` escribe a `~/carter_debug_chain.log` solo si `CARTER_V4_DEBUG_CHAIN=1`. Bueno para debug, pero:
- No hay structured logging (jsonl).
- No hay trace_id por turn.
- Logs de production se pierden (stdout/stderr en subprocess).

**Recomendación**: jsonl trace por turn, con trace_id, user_text, tools, latency, outcome.

### 3.3 Tests

**16 archivos test, 1,717 LOC**. Coverage real:

Bien cubierto:
- `memory.py`
- `safety.py`, `safety_session_allow.py`
- `loop_detection.py`
- `mission_detector.py`
- `verifier_orchestrator.py`
- `profiles.py`
- `skills.py`, `skill_store.py`

**No cubierto** (gaps críticos):
- `Agent.run_turn` end-to-end con mock LLM
- `_execute_tool_calls` chain logic
- `_chain_more_tools` recursion
- `step_planner.plan_turn` con anaphora boost
- `tool_retrieval.select` con embedder real
- Post-LLM heuristics (`_looks_like_surrender`, `emitted_tool_as_text`)
- Reply processors (`strip_planning_leakage`, `rewrite_claim_to_unverified`)
- GUI tools end-to-end (mss + Win32 mocks)

**Recomendación**: agregar test_agent_integration.py con mock LLM, golden paths para C01/C07/C13/C14.

### 3.4 Errores normalizados

`error_classifier.py` existe (141 LOC) pero está poco usado. Cada tool devuelve `{"ok": False, "error": "<string libre>"}`.

**Problema**: el LLM tiene que parsear strings de error para decidir reintentar. No hay tipos de error consistentes.

**Recomendación**: `ToolErrorKind = Literal["NOT_FOUND", "PERMISSION_DENIED", "TIMEOUT", "INVALID_ARG", "INTERNAL"]`. Cada tool devuelve `error_kind` + `error_message`.

---

## 4. Bench como detector de bugs reales

Análisis del bench 54 P0:

### 4.1 FAILs reales (lógicos)

**Ninguno**. Los 3 FAIL son por latencia. El comportamiento funcional es correcto en los 54 casos.

### 4.2 PARTIALs

10 PARTIAL, todos por latencia. Casos típicos:
- C07-01 "abre Bloc de notas": 34s (Notepad++ ya estaba abierto, app_open llamado 2 veces) — **bug latente**: ¿por qué app_open se llama 2 veces?
- C09-02 "revisa si Steam está abierto": 24s (list_windows + LLM follow-up) — esperable.

### 4.3 Insight clave

El bench actual usa **budgets de latencia estrictos** que son inalcanzables con el agent loop actual (1 LLM call por tool). Para que Carter alcance los budgets:
- O reducir LLM calls (mission_goal verifier por estado, no por LLM).
- O acelerar el LLM (modelo más rápido / smaller / streaming usado).

---

## 5. Deuda técnica priorizada

| ID | Issue | Severidad | Esfuerzo | Plan |
|----|-------|-----------|----------|------|
| D1 | agent.py 1397 LOC | **Crítica** | 2 sesiones | Refactor en 8 módulos |
| D2 | 3 routers compitiendo | **Crítica** | 1 sesión | Unificar en core/router.py |
| D3 | Per-app hardcodes step_planner | **Alta** | 0.5 sesión | Mover a registry universal |
| D4 | CORE_PROMPT 3400 tokens | **Alta** | 0.5 sesión | Cortar a <1500 |
| D5 | Verifier por-tool, no por-misión | **Alta** | 1 sesión | Crear `verify/mission_goal.py` |
| D6 | Latencia 1-tool 16s vs 8-12s target | **Crítica** | 1 sesión | Reducir overhead post-tool |
| D7 | Sin integration tests del agent loop | Alta | 0.5 sesión | mock LLM + golden paths |
| D8 | 4 tests fallando | Baja | 0.1 sesión | Fix strings |
| D9 | 3 funciones `select_profile` mismo nombre | Media | 0.2 sesión | Renombrar |
| D10 | Falta tracing estructurado | Media | 0.3 sesión | jsonl trace per turn |
| D11 | Cold start 21s | Media | 0.3 sesión | Eager-load embedder |
| D12 | Error_classifier infrautilizado | Baja | 0.3 sesión | Normalizar error_kind |

**Total esfuerzo estimado para implementación 10/10**: ~7 sesiones de trabajo enfocado.

---

## 6. Criterios para implementación 10/10

Solo declaro 10/10 cuando:

- [ ] agent.py < 600 LOC, leíble sin abrir otros archivos.
- [ ] **Cero duplicación crítica** (grep `select_profile`, `detect_destructive` → 1 resultado cada uno).
- [ ] **Tests pass**: 140+ unit + 20+ integration con mock LLM.
- [ ] **Bench P0 ≥85%** con mismo budget.
- [ ] **Latencia 1-tool ≤12s** medida (50% reducción de 16s actual).
- [ ] **Tracing jsonl** por turn.
- [ ] **Pydantic schemas** para MissionGoal, OutcomeState, ToolResult.
- [ ] **Cold start <8s** (eager load embedder en __init__).
- [ ] **Error_kind normalizado** en todas las tools.
- [ ] **CORE_PROMPT <1500 tokens** medido.

Score actual: **6/10**. Distancia a 10: 12 issues, ~7 sesiones de refactor disciplinado.
