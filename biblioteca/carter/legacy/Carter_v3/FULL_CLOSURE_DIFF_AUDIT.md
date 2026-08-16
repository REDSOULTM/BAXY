# FULL_CLOSURE_DIFF_AUDIT

Fecha: 2026-05-06

## Alcance del diff

Este diff parte de un working tree ya sucio antes de la auditoría. Se preservaron y se corrigieron los cambios preexistentes en vez de sobrescribirlos.

## Cambios preexistentes conservados

- `agent.py`: validación de launch directo, guard de script mismatch, no registrar `app_close` reciente salvo confirmado, missing capability más honesto.
- `llm_verbalizer.py`: soporte de prior turns alternativo y restricciones contra workarounds externos.
- `response_composer.py`: app_close `already_absent` honesto.
- `session_state.py`: `display_name` como target reciente.
- `tools/verifier.py`: `app_close already_absent` como pending, no confirmed.
- `turn_support.py`: prompt más estricto contra workarounds y claims de inspección sin evidencia.

## Cambios implementados en esta auditoría

### Baseline / no fake success

- `agent.py`:
  - `_should_keep_structural_tool_reply()` ya no salta LLM-first para todos los app tools; solo conserva el scaffold para `app_close` con `already_absent`.
- `tests/test_verifier_actions.py`:
  - `already_absent` espera `PENDING` + evidencia, no `CONFIRMED`.

### Local reminders

- Nuevo `src/carter_v3/tools/local_reminders.py`:
  - SQLite local.
  - `create/list/get/cancel/cleanup_expired`.
  - persistencia local.
  - reject past due dates.
  - evidencia `notification_backend=local_store_only` y `os_notification_scheduled=False`.
- `tools/catalog.py`:
  - Nueva tool pública `local_reminder`.
  - Cap público se mantiene `<=32` retirando `system_get_time` del catálogo público.
- `tools/dispatch.py` y `tools/dispatch_misc.py`:
  - Registro y handler de `local_reminder`.
- `tools/verifier.py`:
  - Verifier específico de store local.
- `response_composer.py`:
  - Replies específicos para recordatorios locales.
- `llm_verbalizer.py`:
  - Restricciones para no prometer OS alarm, system notification ni calendar externo.

### Local state questions

- `agent.py`:
  - `_has_local_state_question_shape()` para preguntas amplias de estado local.
  - Scope de tools read-only/locales para consultas tipo estado local, sin tokens alarm/reminder.
  - No se guardan estas preguntas como memory offer accidental.
- `tests/test_agent_integration.py`:
  - Cobertura de pregunta local read-only (`network_get_ip`).
- `tests/test_local_reminders.py`:
  - Cobertura de status/list de recordatorios.

### Tests convertidos/agregados

- `tests/test_local_reminders.py` nuevo.
- `tests/test_memory_runtime_consistency.py`:
  - Test antiguo de “alarm missing” pasa a create verificado de `local_reminder`.
- `tests/test_runtime_no_fake_success_live_cases.py`:
  - Test antiguo de delayed missing capability pasa a create local sin terminal workaround.
- `tests/test_agent_integration.py`:
  - Nueva regresión para local-state read-only tools.

### Runners/smokes alineados

- `audit/full_matrix_runner.py`:
  - `TOOL_FAMILY['local_reminder']`.
- `audit/smoke_manual_equivalent.py`:
  - Create/list de local reminders reales.
- `audit/smoke_live_strict.py`, `audit/smoke_live_cycle_5.py`, `audit/smoke_live_post_cleanup.py`:
  - Alarm/reminder ya no se clasifica como missing capability sino como local reminders.
- `MANUAL_LIVE_AFTER_LLM_FIRST_SMOKE_RESULTS.md` y `MANUAL_EQUIVALENT_SMOKE_RESULTS.md`:
  - Actualizados a 18/18 PASS con local reminders.

## Artifacts conservados

- `audit/runs/full_closure_cycle2_minimum_final_v2.json`.
- `audit/runs/full_closure_cycle2_full_matrix_final.json`.

## Artifacts removidos

Se eliminaron DBs temporales y JSONs intermedios/fallidos/probes para no contaminar el diff final:

- `audit/full_closure_cycle2_*.memory.db` intermedios.
- `audit/runs/full_closure_cycle2_*` intermedios, excepto los dos artifacts finales citados arriba.

## Diff stat final observado

`git diff --stat` mostró 20 tracked files modificados con 344 insertions y 66 deletions antes de contar archivos nuevos no tracked.

Archivos nuevos intencionales:

- `src/carter_v3/tools/local_reminders.py`
- `tests/test_local_reminders.py`
- `FULL_CLOSURE_BASELINE.md`
- `FULL_TEST_CAPABILITY_MAP.md`
- `FULL_CODE_AUDIT.md`
- `FULL_CAPABILITY_IMPLEMENTATION_PLAN.md`
- `FULL_CLOSURE_CYCLE_1_REPORT.md`
- `FULL_CLOSURE_CYCLE_2_REPORT.md`
- `FULL_CLOSURE_CYCLE_3_REPORT.md`
- `FULL_CLOSURE_CYCLE_4_REPORT.md`
- `FULL_CLOSURE_DIFF_AUDIT.md`
- `CARTER_V3_FULL_TRUE_READY_REPORT.md` (creado después de este diff audit)

## Hardcode audit del diff

- No se introdujo routing por `alarm`/`reminder`.
- No se agregaron helpers `looks_alarm_request` ni equivalentes.
- Los tokens de alarm/reminder aparecen como:
  - nombre real de capability/tool;
  - tests;
  - audit reports/smoke oracles;
  - parser temporal interno post-selección de tool.
- `audit/hardcode_guard.py`: clean, 58 files scanned.
- `tests/test_no_semantic_hardcodes.py`: 17 passed.

## Veredicto del diff

`DIFF_ACCEPTED_FOR_FULL_TRUE_READY`
