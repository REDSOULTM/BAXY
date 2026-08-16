# FULL_CLOSURE_CYCLE_3_REPORT

Fecha: 2026-05-06

## Objetivo

Cerrar la capacidad de status/list para recordatorios y alinear runners smoke heredados que todavía esperaban “alarma no disponible”.

## Fallos observados

1. `audit/smoke_manual_equivalent.py` pasó a 17/18:
   - Create de recordatorio local pasaba.
   - La consulta “para cuando tengo una alarma?” no recibía scope de tools y terminaba en chat trivial.
2. Probe de full matrix categoría 6 detectó un fallo en un prompt de estado local:
   - Prompt: `qu� adaptadores de red tengo`.
   - El LLM respondió con workaround de terminal sin tool.
   - Validador falló `no_fake_success`.

## Causa real

- Carter solo exponía tools si `looks_action` era verdadero.
- Algunas consultas de estado local son preguntas o texto corto con “tengo” y no entraban en rutas de acción.
- Dejar esas consultas sin scope de tools hacía que el LLM sugiriera comandos o chat genérico en vez de usar capacidades read-only/locales.

## Cambios hechos

1. `agent.py`:
   - Se añadió `_has_local_state_question_shape()` como señal amplia de pregunta de estado local.
   - No contiene tokens alarm/reminder ni nombres de apps/brands.
   - Para esas preguntas se expone un subconjunto seguro de tools locales/read-only:
     - `clock_now`
     - `local_reminder`
     - `memory_recall`
     - `system_get_volume`
     - `system_get_battery`
     - `system_get_cpu_info`
     - `system_get_ram_info`
     - `system_get_gpu_info`
     - `network_get_ip`
     - `process_list`
     - `window_list`
   - Las preguntas de estado local no se guardan como “memory offer” accidental.
   - Si no hay tool, la respuesta cae a missing capability honesto.
2. Tests:
   - `test_agent_local_reminder_status_question_gets_local_tool_scope`.
   - `test_local_state_question_exposes_readonly_system_tools`.
3. Smoke/audit scripts:
   - `smoke_manual_equivalent.py` ahora valida create/list de `local_reminder`.
   - `smoke_live_strict.py`, `smoke_live_cycle_5.py`, `smoke_live_post_cleanup.py` ahora clasifican alarm/reminder como capacidad local, no como missing capability.
4. Reportes smoke actualizados:
   - `MANUAL_LIVE_AFTER_LLM_FIRST_SMOKE_RESULTS.md`.
   - `MANUAL_EQUIVALENT_SMOKE_RESULTS.md`.

## Validación del ciclo

- Focused routing tests + LLM-first subset: 15 passed.
- `audit/hardcode_guard.py`: clean, 58 files scanned.
- `tests/test_no_semantic_hardcodes.py`: 17 passed.
- `audit/smoke_manual_equivalent.py`: 18/18 PASS.
- Probe categoría 6 final:
  - `audit/full_matrix_runner.py --mode live-safe-all --category 6 --label full_closure_cycle2_cat6_probe_v2`
  - Resultado: global 100.0%, p95 2077.6ms.

## Resultado

`CYCLE_3_STATUS_AND_SMOKE_ALIGNMENT_COMPLETE`
