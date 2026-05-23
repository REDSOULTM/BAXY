# Caza de flakiness — sesión de validación final 2026-05-21

Un test no-determinístico que pasa hoy y falla mañana envenena la confianza de la
suite. Objetivo: cazarlos con repeticiones acotadas y arreglar la causa raíz.

## Restricción de método

El `pytest gemma4_agent/ -q` de directorio entero crashea por un access-violation
NATIVO de torch/onnx/sounddevice en cierto orden de colección (gotcha documentado,
PRE-existente, NO un fallo de test). Por eso no se puede hacer el "x20" literal
sobre toda la suite en un proceso. En su lugar corrí **20× cada uno de dos batches
que concentran TODO el riesgo de no-determinismo**: concurrencia, threads, timing,
random/fuzz, lifecycle, y estado global compartido — que es donde la flakiness
vive de verdad. Tests puramente declarativos (contracts, parsing) no son candidatos.

## Batch 1 — concurrencia / lifecycle / fuzz / timing (el de mayor riesgo)

`test_semantic_router_concurrency`, `test_lazy_load_thread_safety`,
`test_shared_manager_lifecycle`, `test_mcp_registry_singleton`,
`test_llama_server_log_handles`, `test_no_orphan_resources`,
`test_primitives_fuzz` (random sembrado), `test_forced_retry_info_guard`,
`test_architectural_invariants`, `test_microagents_cache` (mtime/fs),
`test_voice_pipeline_stop_reset`, `test_voice_runner_tts_reenable`.

**Resultado: 20/20 verde** — 56 passed cada corrida, tiempos estables (12-14s).

## Batch 2 — lógica amplia (router/planner/tools/persistencia/diagnósticos)

`test_router`, `test_intent_router`, `test_modes_timeout`,
`test_modes_info_routing`, `test_planner_read_write`,
`test_tool_dispatch_contract`, `test_tool_call_rescue`,
`test_experience_corruption_recovery`, `test_telemetry_autorotate`,
`test_state_safety`, `test_state_purge`, `test_loop_detection_robustness`,
`test_tracing_failsafe`, `test_smoke_overnight`.

**Resultado: 20/20 verde** — 125 passed + 3 subtests cada corrida, tiempos
estables (11-12s).

## Veredicto

**40 corridas consecutivas, 0 fallos, 0 flakies.** No hubo causa raíz que
arreglar — la suite es determinista en su superficie de mayor riesgo. Esto es
esperado y deseado: los tests del audit usan random SEMBRADO (test_primitives_fuzz
con `random.Random(seed)` fijo), locks reales (no sleeps de carrera), y estado
aislado (tmpdir + setUp/tearDown que limpian singletons como `_SHARED_MANAGER`,
`_MICROAGENT_CACHE`, `_VERIFIERS`).

Por qué NO hay flakiness por diseño:
- **Concurrencia:** los tests de race usan ThreadPoolExecutor con un `time.sleep`
  DETERMINISTA para ensanchar la ventana + assert sobre el invariante (build
  count == 1), no sobre el timing.
- **Random:** todo fuzz va sembrado.
- **Estado global:** cada test que toca un singleton lo resetea en setUp/tearDown.
- **Filesystem:** `test_microagents_cache` usa `os.utime` explícito para forzar el
  cambio de mtime (no depende del reloj de pared).

Único "warning" recurrente: el `UserWarning` de torchvision (image extension no
cargada) — cosmético, ambiental, no afecta resultados.
