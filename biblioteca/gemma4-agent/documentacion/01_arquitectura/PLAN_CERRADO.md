# Plan de optimización Baxy — Cerrado

**Fecha de cierre:** 2026-05-17
**Rama:** `PortandoLoMejor`
**Último commit del plan:** `015e1fc` (Sprint 6.4 followup) + commit del log de Sprint 6.

## Resumen

| Sprint | Tarea principal | Resultado |
|---|---|--:|
| 0 | `requirements.txt` + `pyproject.toml` | +85 LOC, infra reproducible |
| 1 | Quick wins puros (Carter handoff, 23 legacy tool wrappers, etc.) | −3 883 LOC |
| 2 | Instrumentación: tres `trace.event` nuevos + `scripts/analyze_traces.py` | +684 LOC |
| 3a | Matar NLI stack + planner regex ES+EN + grounding fallbacks es+en | −1 691 LOC |
| 4 | `_shared.py` (redact + hard_gate) + `_TurnRequest` + remover Timeline | −162 LOC |
| 5a | Red de tests de contrato para los 4 god classes | +1 993 LOC, +83 tests |
| 5b | Splits seguros (4 done, 6 skip por falta de red de tests) | +966 LOC mover |
| 6 | Desbloquear 5b: 5 extracciones, 24 tests nuevos, 3 SKIPs documentados | +1 070 LOC mover |

**Sprint 3b** (datos de uso real) queda **intencionalmente diferido** —
se ejecuta cuando el operador acumule 7-10 días de uso con la
instrumentación de Sprint 2 (`persona_active` / `microagent_matched` /
`skill_loaded`).

## Métricas finales

### LOC totales
- **Baseline (pre-Sprint 0):** ~55 633 LOC
- **Cierre (post-Sprint 6):** ~53 800 LOC — *neto del plan: −1 833 LOC*
  (las extractions de Sprints 5b/6 añadieron boilerplate; el grueso del
  ahorro fue Sprint 1+3a+4)

### Tests
- **Baseline:** 80 tests, 1 failure pre-existente
- **Cierre:** 742 tests verde, 1 failure pre-existente (la misma del baseline:
  `test_planner_continuation::test_without_hint_short_reply_subset_empty`)
- **Tests de contrato agregados (Sprints 5a + 6):** 107
  (83 contract + 24 pipeline)

### LOC por archivo clave

| Archivo | Baseline | Cierre | Δ |
|---|--:|--:|--:|
| `agent.py` | 2 968 | **1 930** | −1 038 |
| `tools.py` | 4 825 | 4 282 | −543 |
| `domain_tools.py` | 10 539 | 10 539 | 0 (top-level ya estaba limpio; ver Sprint 4) |
| `ui/main_window.py` | 1 430 | 1 616 | +186 (no se splittió; cambios externos pre-existentes incluidos por Sprint 5a) |
| `ui/settings.py` | 1 148 | 1 247 | +99 (idem) |
| `agent_runner.py` + `ui/agent_thread.py` | 772 | 772 | 0 (no se colapsaron) |

### Nuevos módulos (que antes no existían)

| Archivo | LOC | Propósito |
|---|--:|---|
| `_shared.py` | 153 | `redact_sensitive` + `hard_gate` + `TurnRequest` + `fmt_tool_args` |
| `agent_prompt.py` | 560 | `CORE_PROMPT` + `TOOL_RULES` + `build_system_prompt` |
| `agent_guards.py` | 371 | 6 `_guard_*` puros + `build_user_facing_fallback` |
| `agent_compaction.py` | 223 | 8 helpers de compaction puros + 3 constantes |
| `agent_dispatch.py` | 207 | `execute_calls_sequential` + `execute_calls_parallel` |
| `app_resolver.py` | 418 | `AppResolver` + `AppCandidate` |
| `tool_schemas.py` | 79 | `COMPOUND_TOOL_SCHEMAS` literal (65 schemas) |
| `ssrf_guard.py` | 64 | `_is_private_host` + `_SSRFGuardRedirectHandler` |
| `task_runner.py` | 88 | Routine + watcher runners unificados (Sprint 1.8) |

### Eliminaciones notables

| Archivo / componente | LOC | Sprint |
|---|--:|---|
| `gemma4_agent/design_handoff_carter_field/` | 3 980 | 1 (Carter dead static) |
| `capability_classifier.py` + `nli_service.py` + `_ml_import_lock.py` | 598 | 3a (NLI cache hit 3.2% < 20% kill) |
| Planner regex PT/FR/IT-only | ~162 | 3a (CORE_PROMPT ES-only) |
| `timeline.py` (`TimelineWriter`) | 137 | 4 (sinks 4→3) |
| 23 entries legacy en `ToolRegistry._impls` | ~25 | 1.3 |

## God classes restantes (acoplamiento intencional)

Las 4 god classes que el plan identificó como targets están en uno de
dos estados al cierre:

### Dominadas: `Gemma4Agent` + `ToolRegistry`

- **`Gemma4Agent`** (2 968 → 1 930 LOC, −35%): partido en
  `agent_prompt`, `agent_guards`, `agent_compaction`, `agent_dispatch`.
  El loop principal (`run_content`) sigue en `agent.py` pero ahora
  llama a funciones puras nombradas en lugar de tener el comportamiento
  inline.
- **`ToolRegistry`** (parte de `tools.py` 4 825 → 4 282, −11%): extraídos
  `AppResolver`, `SSRF guard`, `COMPOUND_TOOL_SCHEMAS` literal. La
  pipeline de `execute()` (`_normalize_tool_result`, `_coerce_and_validate_tool_args`,
  `_PRE_VALIDATORS`, `_parameters_for_tool`) **se quedó en tools.py**
  por cycle complexity con 5 helpers privados; sus 24 tests de contrato
  (Sprint 6.5) pinean el comportamiento por si un futuro intento lo
  retoma.

### Intactas (decisión explícita): `MainWindow` + `SettingsDialog`

- **`MainWindow`** (1 616 LOC, 55 métodos): 15+ state attrs compartidos
  entre signal handlers. Splitearla requiere o threading state por cada
  signature o un shared state container — no es un split mecánico,
  es un refactor.
- **`SettingsDialog`** (1 247 LOC, 22 métodos, 11 tabs): tabs comparten
  widget refs vía `self` para `_gather()`. Split por tab requiere
  rediseñar la persistencia, no sólo mover código.

### Bonus: workers (`AgentRunner` + `AgentWorker`)

- **`agent_runner.py` (552 LOC)** + **`ui/agent_thread.py` (220 LOC)**:
  divergen genuinamente en threading model (`Thread` vs `QThread`),
  output channel (`BUS.publish` vs `pyqtSignal`), build sequence
  (autostart server + warmup + KV prewarm + vision_relaunch wiring vs
  ServerBootWorker delegation + health-poll loop). Sprint 4 ya escribió
  ~440 LOC de justificación de por qué no se colapsan; Sprint 6 confirmó.

## Lo que NO se hizo y por qué

| Tarea | Razón |
|---|---|
| Sprint 3b (datos personas/microagents/skills) | Espera 7-10 días de uso real con la instrumentación de Sprint 2 |
| Borrar 45 "tools sin uso" | Decisión consciente: el agente apunta a **uso total del PC**; 5 días no son baseline confiable |
| Splittear `MainWindow` / `SettingsDialog` | Acoplamiento intencional, splits requieren rediseño |
| Colapsar `AgentRunner` ≡ `AgentWorker` | Divergencia genuina, parity tests no cubren flujo interno |
| Extraer dispatch pipeline de `tools.py` | Cycle con 5 helpers privados internos; ganancia cosmética |
| Eliminar `TraceLogger` (50+ call sites) → `LogRecorder` | Migración masiva con riesgo de regresión en observabilidad; `scripts/analyze_traces.py` depende del shape actual |
| Refactor de los 4 compaction methods | Tests `test_context_overflow.py` (8 tests) no cubren flujo interno con suficiente granularidad |

Las 7 decisiones están justificadas en sus respectivos `_sprintNN_log.md`.

## Lo que valdría hacer si vuelve a haber energía

En orden de ROI:

1. **Sprint 3b cuando los logs tengan datos** (7-10 días después de
   instrumentación):
   - Eliminar personas/microagents/skills que no aparezcan en ≥1%
     de los turns.
   - Re-evaluar las 45 "tools sin uso" con muestra estadísticamente
     significativa.

2. **Tests de flujo interno para los workers** + colapsar:
   - Si Sprint 7 escribe tests de `_build_agent` (boot ordering),
     `_progress_forwarder` (output ordering), `_run` (loop semantics)
     que sean robustos sin llama-server real, el AgentSerialBase
     se vuelve seguro de extraer.

3. **Cleanup de helpers privados en tools.py**:
   - `_DISPATCH_OK_COMPLETIONS`, `_err`, `_truncate`,
     `_has_unverified_signal`, `_result_evidence` podrían moverse
     a un `tool_internals.py`. Después la extracción del dispatch
     pipeline (Sprint 6.6 skipeado) se vuelve mecánica.

4. **Eliminar TraceLogger** hacia `LogRecorder` solo:
   - Requiere migrar 50+ call sites en `agent.py` + extender
     `LogRecorder` para capturar fuera del HTTP server context (chat.py
     CLI). Mucho trabajo coordinado para ganancia de deduplicación.

5. **Tests-first de UI**:
   - Si `MainWindow.closeEvent`, los signal handlers, y los key
     widget interactions ganan tests con QtBot, splitear por
     sub-widget se vuelve mecánico.

Ninguno de estos es urgente. El estado actual del repo es
**production-stable** y **maintainable**.

## Cómo invocar los sprints (referencia)

Cada sprint tiene su propio `_sprintNN_log.md` con SHAs de commits,
LOC delta, BUG_FOUND, y razones de cada SKIP. El orden de lectura
recomendado para entender una decisión:

1. `_overnight_log.md` (Sprints 0+1)
2. `_sprint2_log.md` + `_sprint2_usage_report.md`
3. `_sprint3a_log.md`
4. `_sprint4_log.md`
5. `_sprint5a_log.md`
6. `_sprint5b_log.md`
7. `_sprint6_log.md`

Los **prompts** correspondientes (que la persona ejecutó copy/pasteándolos
al agente) están en la misma carpeta como `sprint_*.md`.

## Lecciones del plan

1. **Tests-first paga**. Sprint 5a escribió 83 tests de contrato; sin
   ellos Sprints 5b y 6 no habrían podido moverse con confianza. La
   regla "GREEN → REFACTOR → GREEN" detectó 5 tests rotos a tiempo en
   6.4 que se ajustaron sin tocar producción.
2. **SKIP es una decisión válida**. El plan terminó con ~8 tareas
   skipeadas explícitamente. Cada SKIP tiene razón documentada, y eso
   es preferible a forzar un split que rompa observabilidad o UX.
3. **God classes ≠ accidental coupling**. Los UI god classes y los
   workers reflejan acoplamiento real del dominio. La métrica "LOC por
   archivo" no es la métrica correcta para todo.
4. **La instrumentación primero, el refactor después** (Sprint 2 antes
   de Sprint 3a). Sin trace events nuevos, el reporte de uso no podía
   detectar "esta feature no se usa".
5. **Lessons learned se aplican**: el commit hygiene incident de
   Sprint 5b (8fbf30e arrastró WIP via `git add -A`) llevó a la regla
   #9 de Sprint 6 (siempre `git add <archivos_específicos>`).

Plan cerrado.
