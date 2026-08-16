# LIVE_RUNTIME_CYCLE_5_REPAIR_PLAN

Fecha: 2026-05-05

Objetivo: cerrar blockers finales de Cycle 4 sin hardcodes y con cambios mínimos.

## Cambio 1/3 (FIX_NOW): smoke evaluator estructural para Cycle 5

- Archivo: `audit/smoke_live_cycle_5.py`
- Por qué es universal: evalúa por comportamiento (honestidad, capability missing, refusal safety, pending follow-up) y no por frases exactas ni apps hardcodeadas en core de Carter.
- Por qué NO es hardcode: no toca routing del agente ni añade ramas `if user_text == ...` en producción; solo clasifica resultados del harness.
- Tests: `python audit/hardcode_guard.py`, `python -m pytest tests/test_no_semantic_hardcodes.py -v`.
- Smoke case: re-evaluar los FAIL de Cycle 4 (`lee PATH`, `Sí`, `alarma`, `mensajes`, etc.) con criterio estructural.
- Rollback: eliminar `audit/smoke_live_cycle_5.py` y volver a evaluación previa.

## Cambio 2/3 (NOOP): core runtime sin cambios

- Archivo: N/A
- Por qué es universal: los fallos restantes de Cycle 4 no muestran un bug estructural nuevo del core; eran principalmente clasificación de harness o límites honestos/out-of-scope.
- Por qué NO es hardcode: evita introducir fixes por frase para subir pass-rate artificial.
- Tests: validación completa de suites y smoke live final.
- Smoke case: confirmar que `lee PATH + Sí` funciona en live.
- Rollback: N/A.

## Cambio 3/3 (NOOP): tests existentes sin inflado

- Archivo: N/A
- Por qué es universal: la cobertura relevante ya existe (`pending_intent`, `no_fake_success`, `no_semantic_hardcodes`, regresiones live).
- Por qué NO es hardcode: no se agregan asserts de texto literal para prompts puntuales.
- Tests: correr subsets requeridos en Phase 7.
- Smoke case: validación directa contra live runtime.
- Rollback: N/A.
