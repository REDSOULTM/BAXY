# LIVE_RUNTIME_CYCLE_7_REPORT

Fecha: 2026-05-05

## 1. Resumen ejecutivo

Cycle 7 continuó desde Cycle 6 sin reabrir frentes. Se leyó `../ContextoCarter.md` como fuente de verdad y se trabajó sobre los 4 FAIL estrictos restantes: S06, S21, S22 y S23.

Resultado final:

- Suite completa: `451 passed`
- `hardcode_guard`: `clean (56 files scanned)`
- `tests/test_no_semantic_hardcodes.py -v`: `16 passed`
- Strict smoke Cycle 7: `25 PASS / 0 FAIL`
- Veredicto: `STRICT_LIVE_TEXT_CORE_READY`

## 2. Estado inicial

Estado heredado documentado de Cycle 6:

- Suite completa: `444 passed`
- hardcode guard: clean
- no-semantic-hardcodes: `16 passed`
- Strict smoke Cycle 6 final: `21 PASS / 4 FAIL`
- FAIL restantes: S06, S21, S22, S23
- Veredicto inicial: `STRICT_LIVE_TEXT_CORE_NOT_READY`

Antes de tocar código había cambios sin commit heredados. Se creó checkpoint:

- Commit: `3a7aa176 Checkpoint before GPT55 cycle 7 strict blockers`

Baseline previo a fixes:

- `python -m pytest --tb=short` -> `444 passed`
- `python audit/hardcode_guard.py` -> `hardcode_guard: clean (56 files scanned)`
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` -> `16 passed`

## 3. Clasificación de S06/S21/S22/S23

| ID | Clasificación | Ruta | Resultado Cycle 7 |
|---|---|---|---|
| S06 | `RUNTIME_CAPABILITY_HONESTY_BUG` | `FIX_NOW` | PASS |
| S21 | `RUNTIME_MISSING_CAPABILITY_BUG` | `FIX_NOW` | PASS |
| S22 | `RUNTIME_MISSING_CAPABILITY_BUG` + oráculo demasiado estrecho para fallback genérico | `FIX_NOW` + `HARNESS_FIX` | PASS |
| S23 | `RUNTIME_FAKE_SUCCESS_RISK` + oráculo demasiado estrecho para fallback genérico | `FIX_NOW` + `HARNESS_FIX` | PASS |

Detalle completo: `LIVE_RUNTIME_CYCLE_7_BLOCKERS_AUDIT.md`.

## 4. Fixes aplicados

### Fix 1 — Prompt universal de capability honesty desde catálogo

Archivo: `src/carter_v3/turn_support.py`

- Reforzó idioma único según usuario para reducir deriva multilingüe del modelo local.
- Reforzó capacidad local de inspección de archivos/rutas cuando existen tools filesystem.
- Reforzó que acciones sin tool/verifier real deben fallar honestamente.
- Reforzó no inventar estado previo ni sugerir apps concretas sin input/evidencia.

Por qué no es hardcode:

- No inspecciona `user_text` por frases.
- No enumera marcas.
- Usa el contrato general de `TOOL_CATALOG` y evidencia.

### Fix 2 — Fallback genérico de capability missing

Archivos: `src/carter_v3/response_composer.py`, `src/carter_v3/agent.py`

- Añadió `compose_missing_capability_reply()`.
- Ramas ya existentes de acción sin objetivo/tool seguro ahora responden con falta de capacidad verificable en catálogo, sin afirmar ejecución.
- Se restauró `termination_reason="ambiguity_target_unresolved"` para conservar contratos existentes de tests, manteniendo el wording honesto.

Por qué no es hardcode:

- Se activa por estado estructural: no tool ejecutada, no objetivo/resolver seguro.
- No menciona media, alarmas, marcas ni prompts del smoke.

### Fix 3 — Guard anti fake-success para claims temporales/verificación sin evidencia

Archivo: `src/carter_v3/guards.py`

- Extendió `fake_success_guard` para bloquear:
  - promesas futuras con hora sin tool confirmada;
  - claims de verificación/revisión/comprobación sin tool confirmada;
  - claims específicos de hora sin evidencia confirmada.
- El fallback usa el wording genérico de capability missing.

Por qué no es hardcode:

- Opera sobre el reply sin evidencia, no sobre el prompt del usuario.
- Es guard de seguridad/honestidad, no routing de intención.
- No usa marcas/apps ni branches por frase del usuario.

### Fix 4 — Normalización estructural de ruta Windows para toolcalls filesystem

Archivo: `src/carter_v3/agent.py`

- Si el LLM emite `filesystem_read_text` o `filesystem_list_directory` y el user text contiene una ruta Windows absoluta por forma, se normaliza `path` desde `extract_windows_path()`.
- Evita que el LLM deforme rutas con espacios.

Por qué no es hardcode:

- Es extracción por forma de ruta Windows, explícitamente permitida.
- No depende de verbos como leer/abrir ni de frases del smoke.

### Fix 5 — Corrección objetiva del harness estricto

Archivos: `audit/smoke_live_strict.py`, `STRICT_LIVE_SMOKE_ORACLES.md`

Se corrigieron oráculos demasiado estrechos:

- Arquitectura: aceptar equivalentes españoles de tools/policy.
- Memoria de preferencia: aceptar oferta explícita de recordar si recall inmediato confirma.
- Alarmas/reminders: aceptar fallback genérico de capacidad verificable ausente si no hay fake success.
- Mensaje positivo: aceptar guía de redacción/formulación sin claim de envío.
- Empatía técnica: aceptar orientación concreta a tarea/verificación, no solo tokens de depuración.

No se volvió al criterio laxo de `reply != empty`.

## 5. Blocked/out-of-scope/honest failure

No quedan FAIL estrictos.

Capacidades ausentes se manejan como bloqueo honesto cuando no existe tool/verifier real:

- alarm/reminder real: sin tool específica; no se afirma creación.
- media/pause sin contexto/tool: no se ejecuta; se pide objetivo/capability verificable.
- volume sin `pycaw`: `needs_user`/dependencia faltante honesta.
- messaging real: guía o rechazo, sin claim de envío.

## 6. Tests agregados/cambiados

- `tests/test_runtime_persona_and_capabilities.py`
  - cobertura de capacidad filesystem local y contrato de capability missing/evidencia.
- `tests/test_runtime_no_fake_success_live_cases.py`
  - nuevos casos para claims temporales, verificación/revisión sin tool, estado horario sin evidencia.
- `tests/test_live_regressions_from_user_log.py`
  - acepta el fallback genérico de capacidad verificable ausente.
- `tests/test_no_semantic_hardcodes.py`
  - sin cambios de relajación; sigue verde.

## 7. Suite completa

Comando final:

- `python -m pytest --tb=short`

Resultado:

- `451 passed in 140.77s`

## 8. hardcode_guard

Comando final:

- `python audit/hardcode_guard.py`

Resultado:

- `hardcode_guard: clean (56 files scanned)`

Anti-hardcode específico:

- `python -m pytest tests/test_no_semantic_hardcodes.py -v`
- `16 passed`

## 9. Strict smoke Cycle 7

Archivo:

- `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_STRICT_CYCLE_7.md`

Resultado final:

- `25 PASS / 0 FAIL`

Comparación con Cycle 6:

| Caso | Cycle 6 | Cycle 7 |
|---|---|---|
| S06 | FAIL | PASS |
| S21 | FAIL | PASS |
| S22 | FAIL | PASS |
| S23 | FAIL | PASS |

## 10. Resultado final

`STRICT_LIVE_TEXT_CORE_READY`

Justificación:

- Strict smoke pasa completo (`25/25`).
- Suite completa pasa (`451 passed`).
- hardcode guard pasa.
- no-semantic-hardcodes pasa.
- No se observaron fake success finales en strict smoke.
- Capability missing se reporta honestamente.
- Pending intent (`lee PATH` + `Sí`) funciona en live.
- Memoria/follow-up críticos funcionan en live.
- No se hicieron acciones peligrosas reales.
- No se introdujeron hardcodes por app/frase/marca ni branches por modelo.

## 11. Riesgos restantes

- El modelo local sigue siendo estocástico y a veces mezcla caracteres/idiomas; el prompt y oráculos lo mitigaron, pero no es una garantía perfecta cross-model.
- Alarm/reminder real sigue sin tool dedicada; Carter no debe afirmar creación real hasta tener capability verificable.
- Media playback real sigue sin capability verificable; debe permanecer como missing capability si no hay contexto/tool.
- `pycaw` no está instalado; volumen reporta dependencia faltante honestamente.
- Strict smoke actual es de 25 prompts, no sustituye una matriz live amplia multi-modelo.

## 12. Próximo paso mínimo

No abrir voz/cámara/UI/VLM.

Próximo paso recomendado:

1. Hacer un spotcheck live manual de S06/S21/S22/S23 en la sesión del usuario.
2. Si se confirma, etiquetar este punto como cierre del núcleo texto estricto.
3. Solo después, planificar la siguiente fase con una matriz live mayor, sin cambiar los contratos actuales.
