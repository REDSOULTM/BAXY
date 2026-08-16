# FINAL_TEST_DIFF_AUDIT

Veredicto: **DIFF_CLEAN_ACCEPTABLE**

## 1. Archivos modificados

- `src/carter_v3/security/policy.py`
- `src/carter_v3/request_patterns.py`
- `src/carter_v3/agent.py`
- `audit/full_matrix_runner.py`
- `tests/test_agent_integration.py`
- `TEST_FAILURE_AUDIT.md`
- `FINAL_TEST_DIFF_AUDIT.md`
- `TEST_TRUE_READY_REPORT.md`

## 2. Qué cambió

- Policy safety: amplía clases críticas generales para borrado de discos/registro/logs, force-kill, puertos públicos, cambios persistentes del sistema, privilegios/admin, exploits, cuenta, credenciales/cookies/SSH y exfiltración.
- Memory routing: reconoce actualización explícita de `user.name` como memoria local, no como app target.
- Agent control loop:
  - agrega gate universal de ambigüedad cuando un target de una sola palabra sólo aparece como categoría/subtoken dentro de un recurso de inventario;
  - evita `action_route_fallback` si ya hubo policy block;
  - restringe fallback de app a requests con forma app open/close.
- Runner: agrega modo `live-safe-all`, que ejecuta los 654 casos con LLM real y bloquea side effects por policy en vez de saltar casos.
- Test: actualiza expectativa de un caso destructivo natural-language para confirmar bloqueo pre-LLM.

## 3. Por qué es universal

- Los cambios no comparan prompts exactos del test.
- No agregan rutas absolutas del usuario.
- No agregan marcas/apps como rutas de decisión.
- La ambigüedad se decide por forma estructural del resolver: token único dentro de nombre más largo o substring de token de inventario.
- La safety policy agrupa clases de riesgo, no casos aislados.

## 4. Hardcodes por frase/app/ruta

- Frases exactas del test: **no**.
- App/brand hacks: **no**.
- Rutas absolutas: **no**.
- Se mantienen patrones auditados de seguridad y memoria en módulos ya diseñados para eso.

## 5. Regex semánticos

- No se agregaron regex de routing por app/marca.
- Sí se ampliaron regex de **policy de seguridad** y **memoria explícita**, que son clases permitidas por ContextoCarter para bloquear riesgo y manejar datos personales de forma local.

## 6. Policy relajada

- **No**. Policy quedó más estricta.
- `auto_approve_high` no se tocó.
- No se autoaprueban high/critical.

## 7. Validadores relajados

- **No**. No se relajó ningún validator.
- `live-safe-all` elimina skipped; no cambia `_apply_validators()`.

## 8. Artifacts/DB/screenshots

- DBs `gpt55_true_ready_round*.memory.db`: generadas y eliminadas.
- JSONs `audit/runs/gpt55_true_ready_round*.json`: generados, resumidos en reportes y eliminados del diff.
- `screenshot.png`: restaurado; no queda modificado.

## 9. Algo existe solo para pasar el test

- `live-safe-all` existe como modo de validación safety/no-skip. Es general y útil: ejecuta cualquier matriz completa sin side effects reales.
- Los fixes runtime son mecanismos universales de policy, memory y resolver; no son hacks de caso puntual.
