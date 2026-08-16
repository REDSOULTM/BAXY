# FULL_CAPABILITY_IMPLEMENTATION_PLAN

Fecha: 2026-05-06

No se tocará código fuente antes de este plan.

## Prioridades

1. Reparar baseline roto sin perder los cambios útiles preexistentes.
2. Implementar ALARMS_REMINDERS como capability local legítima y verificable.
3. Mantener seguridad/no fake success/no hardcodes.
4. Añadir tests reales unitarios/integración/live-safe donde aplique.
5. Revalidar pytest, hardcode_guard, no_semantic_hardcodes, LLM-first, minimum y full matrix.

## Ciclo 1 — baseline y coherencia app/LLM-first

Máximo 5 cambios:

1. Ajustar `_verbalize_result_reply()` para no saltar LLM verbalizer en `app_open`/`app_close` cuando el resultado es `UNVERIFIED/PENDING/FAILED`; mantener draft estructural solo donde sea necesario y no viole LLM-first.
2. Corregir `_should_keep_structural_tool_reply()` si se conserva: debe ser específico y no impedir el test LLM-first.
3. Mantener `app_close already_absent` como `PENDING` porque no hubo cierre real, alineado con ContextoCarter.
4. Actualizar el test heredado de `already_absent` para exigir `PENDING` + evidencia, documentándolo como mejora de prueba contra fake success.
5. Ejecutar pytest enfocado y completo.

Salida: `FULL_CLOSURE_CYCLE_1_REPORT.md`.

## Ciclo 2 — ALARMS_REMINDERS local real

Máximo 5 cambios:

1. Añadir store local persistente `LocalReminderStore` con SQLite o JSON:
   - default local-only;
   - env var de test `CARTER_REMINDER_DB`;
   - ID único;
   - `title`, `due_at`, `timezone`, `status`, `created_at`, `updated_at`.
2. Añadir una tool pública compuesta `local_reminder` para conservar cap `<=32`:
   - `operation`: `create`, `list`, `cancel`, `get`, `cleanup_expired`;
   - `due_at` ISO o `when_text` opcional para create;
   - `reminder_id` para get/cancel;
   - `title` opcional.
3. Liberar un slot de catálogo retirando `system_get_time` del catálogo público; conservar `clock_now` y handler interno si se necesita compatibilidad.
4. Registrar dispatcher y verifier:
   - create confirma que el registro existe y está active;
   - list/get son read-only/skipped o confirmed por store;
   - cancel confirma status cancelled;
   - reject past devuelve ok=False sin fake success.
5. Añadir composer específico para `local_reminder`, con límite honesto: “guardado/listable localmente por Carter; no prometo notificación del sistema si no hay backend OS”.

Salida: `FULL_CLOSURE_CYCLE_2_REPORT.md`.

## Ciclo 3 — tests de capability y runners

Máximo 5 cambios:

1. Añadir `tests/test_local_reminders.py` con create future, reject past, list, cancel, get, cleanup, persistence restart.
2. Convertir tests existentes de alarm missing en tests de capability real, sin hacerlos depender de frases exactas; usar tool calls estructurados y/o prompt con adapter que emite `local_reminder`.
3. Añadir validación de no fake success si dispatcher falla al guardar.
4. Añadir ALARMS_REMINDERS al mapa/runners si se crea runner category 30; si no, documentar que full matrix actual no lo contiene y que unit/integration cubren la nueva capability.
5. Ejecutar pytest enfocado + hardcode_guard.

Salida: `FULL_CLOSURE_CYCLE_3_REPORT.md`.

## Ciclo 4 — validación completa

Máximo 5 acciones:

1. `python -m pytest --tb=short`.
2. `python audit/hardcode_guard.py`.
3. `python -m pytest tests/test_no_semantic_hardcodes.py -v`.
4. `python -m pytest tests/test_llm_first_responses.py -v`.
5. Ejecutar `minimum_testing_runner.py --mode=live-safe-all --subset=minimum` y `full_matrix_runner.py --mode live-safe-all --model qwen2.5:7b-instruct` si Ollama responde.

Salida: `FULL_CLOSURE_CYCLE_4_REPORT.md`.

## Criterio de diseño para alarms/reminders

- Carter solo afirmará éxito si el recordatorio se guardó y se pudo leer/verificar en su store local.
- Carter no dirá que creó una alarma del sistema ni que notificará a la hora si no hay backend OS real verificado.
- Carter listará/cancelará solo recordatorios creados por Carter.
- No habrá terminal workaround ni Task Scheduler improvisado.
- No habrá `looks_alarm_request`, regex semántico de intención ni hardcode por frase.
- El routing principal será catálogo + tool call del LLM; el parser temporal solo normaliza fechas dentro de la tool.

## Estado esperado después del plan

- `pytest` completo en verde.
- Capacidad local de reminders verificada.
- Tests antiguos de “no puedo alarmas” reemplazados por pruebas de capacidad real.
- `hardcode_guard` y `no_semantic_hardcodes` siguen verdes.
- Sin fake success.
