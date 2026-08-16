# PLAN MARK INSPIRED TEXT CORE

Plan incremental (maximo 3 cambios) alineado con `ContextoCarter.md`.

## Cambio 1: Secuencia canonica de estados internos del turno

- **Objetivo:** mejorar trazabilidad textual del pipeline sin UI ni voz.
- **Archivos a tocar:**
  - `src/carter_v3/trace.py`
  - `src/carter_v3/agent.py`
- **Motivo:** Carter ya emite eventos, pero falta una lectura unificada de estado de alto nivel para auditoria/depuracion.
- **Riesgo:** bajo (solo metadata/trace).
- **Rollback:** revertir cambios en `trace.py` y `agent.py`.
- **Tests a agregar/modificar:** test que valide secuencia de estados registrada en `last_turn_trace`.
- **Criterio de exito:** cada turno expone secuencia clara de estados (`RECEIVED_INPUT`, `CLASSIFYING_INTENT`, etc.) sin afectar comportamiento funcional.
- **Alineacion ContextoCarter:** fortalece trazabilidad y transparencia sin meter complejidad visual.

## Cambio 2: Normalizacion defensiva de resultados de tools

- **Objetivo:** impedir `COMPLETE` por resultados vacios/inconsistentes de dispatch.
- **Archivos a tocar:**
  - `src/carter_v3/agent.py`
- **Motivo:** cerrar vector residual de fake success si un handler devuelve `ok=True` sin evidencia util.
- **Riesgo:** medio-bajo (puede degradar a `UNVERIFIED` casos borderline).
- **Rollback:** revertir helper de normalizacion en `agent.py`.
- **Tests a agregar/modificar:** test donde tool devuelve `ok=True` con payload vacio y verifier confirma; debe degradarse a no-confirmado.
- **Criterio de exito:** ningun camino “vacio” termina en exito fuerte no justificado.
- **Alineacion ContextoCarter:** “no mentir nunca”, “verificar cada accion”.

## Cambio 3: Endurecer suite anti fake success

- **Objetivo:** convertir regresiones de honestidad en fallas de test.
- **Archivos a tocar:**
  - `tests/test_agent_integration.py`
- **Motivo:** blindar invariantes de fase texto.
- **Riesgo:** bajo.
- **Rollback:** revertir tests nuevos.
- **Tests a agregar/modificar:**
  - estado canonico en trace;
  - tool vacia no produce `COMPLETE`;
  - excepcion de dispatcher no queda oculta como exito.
- **Criterio de exito:** pruebas pasan y detectan regresiones fake-success.
- **Alineacion ContextoCarter:** foco total en confiabilidad del nucleo texto.

