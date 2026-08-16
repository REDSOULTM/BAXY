# ULTRA LATENCY AUDIT — Carter v2 (OPUS 4.7)

**Scope:** Read-only L0 audit of every latency-relevant code path and live-safe data file before applying L1–L14 optimizations.
**Baseline label:** `live_safe_postopt2` (qwen3:8b, 654 cases: 452 pass / 3 fail / 199 skip), `pytest 436/436`, `hardcode_guard 0/0`.
**Stretch targets (user-defined):**
- simple p50≤2.5s · p95≤5s · max≤8s
- identity p50≤3s · p95≤6s · max≤8s
- tools_simple p50≤5s · p95≤8s · max≤12s
- app_action p50≤8s · p95≤15s · max≤20s
- mission no-GUI p50≤12s · p95≤25–30s

---

## §1. Veredicto brutal

Carter v2 ya cumple el contrato funcional (P-CONT-1..8 cerrado: `final_verdict=READY 7/7`, sin hardcodes, mission max 457s→131s, tools max 191s→92s) **pero NO cumple los stretch targets de Jarvis local**. Los principales bloqueadores son:

1. **GUI UIA observación variable (Tier 2):** `mission` p95 = 32s; outliers C12.13/C12.34/C12.14 entre 32 y 131 s. UIA reintentos sin time-budget claro y sin fallback inmediato a screenshot+OCR.
2. **Terminal timeout uniforme 60 s:** `_DEFAULT_TIMEOUT=60` (terminal.py:99). Cualquier sub-comando trivial (apertura de shell, comando inválido) consume hasta 60 s. C10.17 = 91s (`wallclock_budget_exceeded`).
3. **Filesystem `start <archivo inexistente>`:** sin pre-check; el sistema lanza el ejecutable y espera timeout (C9.37 = 64s, classification `action_failed_single_tool_environment`).
4. **Backend Ollama sin tuning fino:** `OpenAICompatAgentBackend.timeout=180.0` global; `num_ctx=16384` fijo; `num_predict`/`keep_alive`/`top_p` **no expuestos**. C1.01 ("hola") = 70s con reply real `LLM error after 3 attempts: timed out` → no es cold-start, es backend mal configurado en arranque.
5. **Trazas insuficientes para diagnosticar:** no hay `prompt_build_ms`, `tool_exec_ms` por herramienta, `vision_ms`, `vision_tier_used`, ni `llm_call_ms`. Sin estos campos cualquier optimización es ciega.
6. **Catalog tool tokenization no cacheada:** `tool_catalog_selection.py` recalcula `_tool_tokens()` en cada turno (242 schemas × ~20 tokens). Marginal en milisegundos pero acumulativo.

**Calidad / seguridad / verificación:** intactas. La oportunidad es puramente de **latencia** sin tocar comportamiento ni semántica.

---

## §2. Top slow cases (live_safe_postopt2)

| # | CID | ms     | Profile             | Termination                            | Causa raíz                                     |
|---|-----|--------|---------------------|----------------------------------------|------------------------------------------------|
| 1 | C12.13 | 131374 | mission             | partial_after_app_open / gui_do failed | GUI_OBSERVATION_SLOW (UIA reintentos)          |
| 2 | C10.17 | 91742  | tools_simple        | wallclock_budget_exceeded              | TOOL_TIMEOUT (terminal sin per-cmd timeout)    |
| 3 | C12.34 | 71993  | mission             | partial / GUI variance                 | GUI_OBSERVATION_SLOW                           |
| 4 | C1.01  | 70054  | simple              | "LLM error after 3 attempts: timed out"| BACKEND_SAMPLING_SLOW + STARTUP_OVERHEAD       |
| 5 | C9.37  | 64338  | filesystem          | action_failed_single_tool_environment  | IO_OPERATION_NATURALLY_LONG (file not found)   |
| 6 | C12.14 | 32046  | mission             | ok_or_unclassified                     | GUI_OBSERVATION_SLOW (variance)                |
| 7 | C3.16  | 10883  | concept_explanation | ok                                     | aceptable; respuesta LLM extensa               |

**Patrón:** 6 de 7 casos lentos concentrados en GUI/terminal/filesystem (1.3 % del total). Una vez tratados, el p95 cae bajo el target en cada perfil.

---

## §3. Latencia por categoría (baseline vs target)

| Categoría             | p50 actual | p95 actual | max actual | Target stretch p50/p95/max | Estado     |
|-----------------------|------------|------------|------------|----------------------------|------------|
| simple                | 559 ms     | 2 000 ms   | 70 054 ms  | 2.5 / 5 / 8 s              | p50/p95 OK; max FAIL (C1.01) |
| identity              | 1 358 ms   | 2 412 ms   | 2 412 ms   | 3 / 6 / 8 s                | OK         |
| concept_explanation   | 3 670 ms   | 7 537 ms   | 10 883 ms  | (knowledge ~ tools) 5/8/12 | OK / borderline |
| tools_simple          | 1 221 ms   | 4 230 ms   | 91 742 ms  | 5 / 8 / 12 s               | p50/p95 OK; max FAIL (C10.17) |
| app_action            | 1 453 ms   | 5 389 ms   | 6 929 ms   | 8 / 15 / 20 s              | OK         |
| mission (con GUI)     | 3 366 ms   | 32 046 ms  | 131 374 ms | (no-GUI) 12 / 25–30 / 30   | p50 OK; p95 FAIL; max FAIL |
| chitchat              | 405 ms     | 858 ms     | 858 ms     | n/a                        | OK         |

---

## §4. Latencia por etapa (faltan métricas; las inferimos de código + outliers)

| Etapa                  | Donde está                                          | Coste estimado     | Bottleneck? |
|------------------------|-----------------------------------------------------|--------------------|-------------|
| prompt_build           | `_system_prompt.py` (cache SHA256 64-FIFO)          | 1–5 ms (cache hit) | NO          |
| memory_retrieval       | `session/memory.py` (SQLite)                        | 5–20 ms            | NO          |
| context_window         | `universal/context.py`                              | <5 ms              | NO          |
| active_app_context     | `perception.py` (window enumeration)                | 10–80 ms           | LOW         |
| tool_catalog_select    | `tool_catalog_selection.py` (242 schemas scoring)   | 5–15 ms            | NO          |
| semantic_decision      | `intent_resolution.py` (regex + heuristic)          | <2 ms              | NO          |
| llm_call (ollama)      | `backends.py` (timeout=180s, num_ctx=16384)         | 500 ms – 180 s     | **YES**     |
| tool_exec              | `capabilities/*.py`                                 | 10 ms – 60 s       | **YES** (terminal/GUI) |
| observation (UIA)      | `mission_observation.py` Tier 2                     | 100 ms – 30 s      | **YES**     |
| vision (omniparser/llm)| `vision_router.py`                                  | 500 ms – 5 s       | LOW         |
| retry_loop             | `agent.py` (con repeat_failure_break)               | aplicado P-CONT-7  | NO          |
| mission_loop           | `agent.py` + `mission.py`                           | dominado por obs.  | n/a         |
| verification           | `mission_verification.py`                           | 5–50 ms            | NO          |

**Conclusión:** los únicos bottlenecks reales son **llm_call**, **tool_exec (terminal/GUI)** y **observation (UIA)**.

---

## §5. Causas raíz mapeadas

| Código                       | Categoría afectada           | Donde se ve              |
|------------------------------|------------------------------|--------------------------|
| GUI_OBSERVATION_SLOW         | mission con GUI              | C12.13 / C12.34 / C12.14 |
| TOOL_TIMEOUT                 | tools_simple, terminal       | C10.17                   |
| BACKEND_SAMPLING_SLOW        | simple (cold) / cualquier turn| C1.01                    |
| STARTUP_OVERHEAD             | primer turn de la sesión      | C1.01                    |
| IO_OPERATION_NATURALLY_LONG  | filesystem (file not found)  | C9.37                    |
| PROMPT_TOO_LARGE             | n/a (cache OK, ~5 KB stable) | —                        |
| TOO_MANY_LLM_CALLS           | n/a (avg ~0.05/turn live)    | —                        |
| VISION_OVERUSED              | n/a (LLM vision opt-in)      | —                        |
| MISSION_REPLAN_LOOP          | n/a (decompose cacheable)    | —                        |
| ACTIVE_APP_CONTEXT_OVERHEAD  | bajo                          | —                        |
| MEMORY_RETRIEVAL_OVERHEAD    | bajo                          | —                        |
| CATALOG_SELECTION_OVERHEAD   | bajo, pero cacheable          | —                        |

---

## §6. Plan L1–L12 (prioridad por impacto / riesgo)

### Prioridad 1 — Impacto alto, riesgo bajo

- **L8-A · GUI UIA timeout + fast-path screenshot (`mission_observation.py`)**
  Time-budget de UIA por step (≤2 s); si no resuelve, fallback inmediato a screenshot/OCR. **Impacto:** C12.* 30–130 s → 5–10 s. **Riesgo:** bajo (fallback es path válido ya implementado).
- **L6-A · Per-command timeout en terminal (`capabilities/terminal.py`)**
  Diferenciar: launch de shell (cmd/powershell -c, sin args largos) → 10 s; comandos largos (winget/pip/git clone) → 60 s. **Impacto:** C10.17 91s → ≤10s.
- **L6-B · Pre-check de archivo inexistente antes de `terminal start`**
  Si la action es `start <archivo>` y `Path.exists()==False` (o no se halla en safe_path), retornar `[needs_user]` estructurado. **Impacto:** C9.37 64s → <100 ms.
- **L10-A · Per-category backend timeout (`backends.py`)**
  Exponer `set_call_timeout()` desde `agent.py` con: simple=20s, tools=45s, mission=120s. Eliminar el reintento ciego de 3×180s en C1.01. **Impacto:** C1.01 70s → ≤8s.
- **L10-B · Exponer `num_predict` / `keep_alive` (`backends.py`)**
  `num_predict=256` para turns simple/identity (cap output), `num_predict=2048` para mission. `keep_alive="30m"` para evitar cold-load entre cases. **Impacto:** simple p50 559→<400 ms; previene cold reload.
- **L11 · Perf gate agresivo (`audit/runners/performance_gate.py`)**
  Subir umbrales a stretch targets, añadir conteo de `slow_stage`, fail si >5 % de casos > p95 target.

### Prioridad 2 — Impacto medio, riesgo bajo

- **L1 · Trace fields normalization (`turn/agent.py` + `audit/runners/full_live_llm_validation.py`)**
  Añadir: `prompt_build_ms`, `tool_exec_ms` (lista), `tool_calls_count`, `llm_call_ms`, `llm_calls_count`, `observation_ms`, `vision_ms`, `vision_tier_used`, `mission_loop_ms`, `verification_ms`, `slow_stage`, `slow_reason`. Update whitelist `_TRACE_KEYS`.
- **L4 · Tool catalog token caching (`tool_catalog_selection.py` + `capabilities/registry.py`)**
  Cachear `_tool_tokens(schema)` al construir el registry. Selección O(N) en lugar de O(N×T).
- **L2 · Prompt diet + cache hit rate (`turn/_system_prompt.py`)**
  Instrumentar hits/misses. Confirmar que bloques `runtime_deps` y `vision_status` (estables por sesión) no rompen el cache.
- **L5 · Active-app TTL cache (`turn/perception.py`)**
  Re-usar resultado por 1.5 s entre llamadas dentro del mismo turno.
- **L9 · Mission decomposition cache (`turn/mission.py`)**
  `decompose_intent(user_text)` cacheado por hash. La regla estructural ya es barata pero el mission frame builder llama LLM.

### Prioridad 3 — Impacto bajo, diagnóstico

- **L3 · Reducir LLM calls innecesarios (`turn/agent.py`)**
  Si la última tool retorna `ok=True` con un `display` claro y la categoría es `app_action`/`tools_simple`, generar la respuesta final con plantilla determinista (sin LLM extra). Mantener LLM final para mission y concept.
- **L7 · Web context reuse (`capabilities/web.py`)**
  Re-usar Playwright page; cambiar `wait_until="networkidle"` → `"domcontentloaded"` cuando OSI lo permita.

### L12 · Iterate measure-revert

Al terminar L1..L11, re-ejecutar `live_safe` (subset top slow + sampler). Si una optimización degrada calidad o no reduce p95, `git revert` ese commit y registrar en `ULTRA_LATENCY_REPORT.md`.

### L13 · Final re-runs (orden estricto, sin paralelo)

1. `pytest -q` (debe seguir 436/436)
2. `audit/runners/hardcode_guard.py` (debe seguir 0/0 critical)
3. `audit/runners/full_scripted_validation.py` (debe seguir 654/654)
4. `audit/runners/full_live_llm_validation.py --label live_safe_ultra`
5. `audit/runners/skipped_live_validation.py --final-gate`
6. `audit/runners/performance_gate.py` (con stretch targets)
7. `audit/runners/final_gate.py` aggregator → `ULTRA_LATENCY_FINAL_GATE.json`

### L14 · Report final

`ULTRA_LATENCY_REPORT.md` con: §ejecutivo, §antes/después por categoría, §top slow cases comparado, §optimizaciones aplicadas / revertidas, §calidad/no-regresión, §riesgos restantes, §veredicto ∈ {ULTRA_LATENCY_READY · ULTRA_LATENCY_READY_WITH_ENV_LIMITATIONS · NOT_READY}.

---

## Anexo A — Archivos a modificar (mapa)

| Phase | Archivo                                                                                              |
|-------|------------------------------------------------------------------------------------------------------|
| L1    | [src/carter_v2/turn/agent.py](src/carter_v2/turn/agent.py), [audit/runners/full_live_llm_validation.py](audit/runners/full_live_llm_validation.py) |
| L2    | [src/carter_v2/turn/_system_prompt.py](src/carter_v2/turn/_system_prompt.py)                         |
| L3    | [src/carter_v2/turn/agent.py](src/carter_v2/turn/agent.py)                                           |
| L4    | [src/carter_v2/turn/tool_catalog_selection.py](src/carter_v2/turn/tool_catalog_selection.py), [src/carter_v2/capabilities/registry.py](src/carter_v2/capabilities/registry.py) |
| L5    | [src/carter_v2/turn/perception.py](src/carter_v2/turn/perception.py)                                 |
| L6    | [src/carter_v2/capabilities/terminal.py](src/carter_v2/capabilities/terminal.py), [src/carter_v2/capabilities/filesystem.py](src/carter_v2/capabilities/filesystem.py) |
| L7    | [src/carter_v2/capabilities/web.py](src/carter_v2/capabilities/web.py)                               |
| L8    | [src/carter_v2/turn/mission_observation.py](src/carter_v2/turn/mission_observation.py), [src/carter_v2/capabilities/vision_router.py](src/carter_v2/capabilities/vision_router.py) |
| L9    | [src/carter_v2/turn/mission.py](src/carter_v2/turn/mission.py)                                       |
| L10   | [src/carter_v2/turn/backends.py](src/carter_v2/turn/backends.py)                                     |
| L11   | [audit/runners/performance_gate.py](audit/runners/performance_gate.py)                               |
| L13   | (re-runs, no edita código)                                                                           |
| L14   | `ULTRA_LATENCY_REPORT.md`                                                                            |

---

**Fin de L0. Procedo a L1.**
