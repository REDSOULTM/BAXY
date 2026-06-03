# 00 — Delta Inventory (post-plan)

> **Comparación:** baseline `aa99458` (pre-Sprint 0) vs HEAD `7f2eecc`
> (post-Sprint 6, plan cerrado).
> **Fuente:** `git diff --name-status aa99458..HEAD -- 'gemma4_agent/*.py'`.

## 1. Conteo macro de cambios

| Tipo | Cantidad |
|---|--:|
| Archivos `.py` agregados | **45** |
| Archivos `.py` borrados | **1** (`timeline.py`) |
| Archivos `.py` modificados | **24** |
| Total tocado | **70 archivos** |

## 2. Archivos NUEVOS por categoría

### 2.1 Módulos extraídos de god classes (Sprint 5b + 6)

| Archivo | LOC | Extraído de | Sprint |
|---|--:|---|---|
| `agent_prompt.py` | 560 | `agent.py` (CORE_PROMPT + TOOL_RULES + build_system_prompt) | 5b.2.c |
| `agent_guards.py` | 371 | `agent.py` (6 `_guard_*` methods + `_build_user_facing_fallback`) | 6.2 |
| `agent_compaction.py` | 223 | `agent.py` (compaction + `_extract_facts` + `_summarize_history_block`) | 6.3 |
| `agent_dispatch.py` | 207 | `agent.py` (`_execute_calls_*`) | 6.4 |
| `app_resolver.py` | 418 | `tools.py` (`AppResolver` + `AppCandidate`) | 5b.1.a |
| `ssrf_guard.py` | 64 | `tools.py` (`_SSRFGuardRedirectHandler` + `_is_private_host`) | 5b.1.b |
| `tool_schemas.py` | 79 | `tools.py` (literal `COMPOUND_TOOL_SCHEMAS`) | 5b.1.d |
| `_shared.py` | 153 | `tools.py` + `domain_tools.py` (`redact_sensitive`, `hard_gate`) | 4.1 + 4.2 |
| `task_runner.py` | 90 | unificación de `routine_runner.py` + `watcher_runner.py` | 1.8 |
| **Total módulos nuevos extraídos** | **2 165** | | |

### 2.2 Tests nuevos (Sprints 5a + 6 + restauración desde stash)

| Archivo | LOC | Sprint |
|---|--:|---|
| `test_tool_registry_contract.py` | (sprint5a) | 5a.1 |
| `test_gemma4agent_contract.py` | (sprint5a) | 5a.2 |
| `test_agent_workers_parity.py` | (sprint5a) | 5a.3 |
| `test_main_window_contract.py` | (sprint5a) | 5a.4 |
| `test_settings_dialog_contract.py` | (sprint5a) | 5a.5 |
| `test_tool_pipeline_helpers.py` | (sprint6) | 6.5 |
| 22 tests adicionales del stash recovery | varios | recovery |
| **Total tests agregados** | **~107 contract + ~22 recovery** | |

### 2.3 Scripts de probes manuales (recovery del stash, no plan)

`gemma4_agent/scripts/`:
- `e2e_test_streaming.py`
- `probe_all_platforms.py`
- `probe_disney_full.py`, `probe_disney_search.py`, `probe_disney_search2.py`
- `probe_netflix_full.py`, `probe_netflix_hbo.py`
- `probe_streaming_cdp.py`, `probe_streaming_urls.py`

Estos son scripts manuales del usuario (no parte del plan).
Recuperados del stash al arrancar Sprint 1.

### 2.4 Otros nuevos

- `voice/app_inventory.py` (639 LOC) — arrastrado por `git add -A` en Sprint 5b commit `8fbf30e` (documentado como deuda menor en `_sprint6_log.md`).
- `intent_validator.py` y `grounding_gate.py` adelgazado — restaurados desde stash (Sprint 1 recovery), no eliminados en Sprint 3a porque `intent_validator` es regex-only (no NLI) y `grounding_gate` mantiene parte inline sin NLI.

## 3. Archivos BORRADOS

| Archivo | Razón | Sprint |
|---|---|---|
| `timeline.py` (137 LOC) | TimelineWriter eliminado, 4 sinks → 3 | 4.4 |

> **Lo que NO se eliminó pero se planeó:**
> - **`tracing.py` (TraceLogger):** Sprint 4.4 partial — tiene 50+ call
>   sites en `agent.py`, migrar es alto riesgo. Sigue activo.
> - **`telemetry.py`:** opt-in default OFF, 443 LOC, sigue activo
>   esperando uso real para decidir.
>
> **Archivos NLI confirmados como NO existentes en HEAD** (sí se
> mataron en Sprint 3a y no se reintrodujeron):
> - `capability_classifier.py` ❌
> - `nli_service.py` ❌
> - `_ml_import_lock.py` ❌
>
> **Archivos restaurados desde stash que sobrevivieron al kill de NLI:**
> - `grounding_gate.py` (~130 LOC, solo capa inline sin NLI).
> - `intent_validator.py` (141 LOC, regex-only, sin dependencia de NLI).

## 4. Archivos MODIFICADOS clave

| Archivo | LOC baseline | LOC actual | Δ | Sprint principal |
|---|--:|--:|--:|---|
| `agent.py` | 2 968 | **1 930** | **−1 038 (−35 %)** | 5b.2.c + 6.2 + 6.3 + 6.4 |
| `tools.py` | 4 825 | 4 282 | −543 (−11 %) | 5b.1.a + 5b.1.b + 5b.1.d |
| `domain_tools.py` | 10 539 | 10 489 | −50 | tools borradas en Sprint 1.3 (0 caídas) |
| `experience.py` | 489 | 489+ | recovery + provenance fields | recovery |
| `planner.py` | 892 | ~750 | −150 | 3a.2 (regex PT/FR/IT trim) |
| `grounding_gate.py` | 255 | ~130 | −125 | 3a.1 (async NLI layer killed) |
| `routine_runner.py` | 54 | ~15 | −40 | 1.8 (wrapper de task_runner) |
| `watcher_runner.py` | 43 | ~15 | −28 | 1.8 (wrapper de task_runner) |
| `model_info.py` | 153 | 153 | TypedDict → dataclass | 1.7 |
| `ui_field/*.tsx`, `.html` | — | — | 4 strings "carter" → "gemma4" | 1.2 |

## 5. Estructura actual del paquete (post-plan)

```
gemma4_agent/
├── __init__.py                  (5 LOC)
├── _ps.py                       (82 LOC, PowerShell helpers)
├── _shared.py                   (153 LOC, redact + hard_gate compartidos) [NUEVO]
├── _ml_import_lock.py           ────── BORRADO ──────  (Sprint 3a)
├── agent.py                     (1 930 LOC, era 2 968) [REDUCIDO −35%]
├── agent_compaction.py          (223 LOC, extraído de agent.py) [NUEVO]
├── agent_dispatch.py            (207 LOC, extraído de agent.py) [NUEVO]
├── agent_guards.py              (371 LOC, extraído de agent.py) [NUEVO]
├── agent_prompt.py              (560 LOC, extraído de agent.py) [NUEVO]
├── agent_runner.py              (552 LOC, no se colapsó con AgentWorker)
├── app_resolver.py              (418 LOC, extraído de tools.py) [NUEVO]
├── boot_progress.py             (145 LOC)
├── capability_classifier.py     ────── BORRADO ──────  (Sprint 3a)
├── chat.py                      (489 LOC)
├── config.py                    (141 LOC)
├── domain_tools.py              (10 489 LOC, −50)
├── eval_smoke.py                (97 LOC)
├── events_bus.py                (99 LOC)
├── experience.py                (recovery + provenance)
├── explicit_plan.py             (150 LOC)
├── grounding_gate.py            (~130 LOC, era 255 −125 sin async NLI)
├── import_triggercmd.py         (131 LOC)
├── intent_validator.py          (141 LOC, regex-only no NLI)
├── knowledge.py                 (253 LOC)
├── launcher.py                  (485 LOC)
├── llama_server.py              (726 LOC)
├── llm_client.py                (490 LOC)
├── log_recorder.py              (220 LOC, canónico)
├── loop_detection.py            (316 LOC)
├── mcp_server.py                (332 LOC)
├── memory.py                    (187 LOC)
├── microagents.py               (351 LOC)
├── mission_goal.py              (659 LOC, NO TOCADO)
├── mission_outcome.py           (260 LOC, NO TOCADO)
├── modes.py                     (199 LOC)
├── model_info.py                (153 LOC, ahora dataclass)
├── multimodal.py                (134 LOC)
├── nli_service.py               ────── BORRADO ──────  (Sprint 3a)
├── personas.py                  (126 LOC, 6 personas conservadas pendientes de Sprint 3b)
├── planner.py                   (~750 LOC, regex ES+EN solo)
├── prewarm.py                   (140 LOC)
├── profile_watcher.py           (398 LOC)
├── profiles.py                  (532 LOC)
├── project_context.py           (91 LOC)
├── reasoning.py                 (234 LOC)
├── routine_runner.py            (~15 LOC, wrapper de task_runner) [REDUCIDO]
├── safety.py                    (67 LOC)
├── semantic_router.py           (279 LOC)
├── server.py                    (1 519 LOC)
├── sessions.py                  (237 LOC)
├── skills_registry.py           (456 LOC, 10 skills conservados pendientes de Sprint 3b)
├── ssrf_guard.py                (64 LOC, extraído de tools.py) [NUEVO]
├── state.py                     (261 LOC)
├── subagent.py                  (99 LOC)
├── task_runner.py               (90 LOC) [NUEVO]
├── telemetry.py                 (443 LOC, opt-in default OFF, NO TOCADO)
├── timeline.py                  ────── BORRADO ──────
├── tool_schemas.py              (79 LOC, extraído de tools.py) [NUEVO]
├── tools.py                     (4 282 LOC, era 4 825) [REDUCIDO −11%]
├── tracing.py                   (67 LOC, sigue activo: 50+ callers no migrados)
├── verifiers.py                 (690 LOC, NO TOCADO, side-effect decorators)
├── verify_core.py               (191 LOC, NO TOCADO)
├── voice_runner.py              (425 LOC, NO TOCADO)
├── watcher_runner.py            (~15 LOC, wrapper de task_runner) [REDUCIDO]
├── voice/                       (paquete completo, NO TOCADO — frontera nítida)
├── ui/                          (god UI conservada conscientemente)
├── scripts/                     (probes manuales, no parte del plan)
├── data/                        (storage runtime)
└── ...
```

## 6. Resumen del impacto

- **9 módulos nuevos** con responsabilidad focalizada, todos <600 LOC.
- **`agent.py` perdió −1 038 LOC (−35 %)** distribuidos en 4 módulos
  cohesivos.
- **`tools.py` perdió −543 LOC (−11 %)** distribuidos en 3 módulos
  cohesivos.
- **2 wrappers unificados** (`routine_runner.py` + `watcher_runner.py` →
  `task_runner.py`).
- **1 sink de telemetría eliminado** (`timeline.py`).
- **107 tests de contrato nuevos** + ~22 tests más restaurados desde
  stash = 742 tests totales verde (vs 80 baseline).
- **Carter eliminado** del paquete (carpeta + strings + 23 wrappers
  fantasma del `_impls`).
- **65 compound tools intactas.** No se eliminó ninguna capability del
  agente.
