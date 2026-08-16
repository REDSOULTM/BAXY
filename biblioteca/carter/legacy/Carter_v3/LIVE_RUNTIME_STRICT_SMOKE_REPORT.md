# LIVE_RUNTIME_STRICT_SMOKE_REPORT

Fecha: 2026-05-05

## 1. Resumen ejecutivo

Se revocó el `READY` previo y se ejecutó un smoke estricto con oráculos de comportamiento y evidencia.  
No se tocó runtime (`agent.py`, `response_composer.py`, `request_patterns.py`, `turn_support.py` intactos).  
El resultado confirma que el harness anterior era laxo y que todavía hay fallos reales por cerrar.

## 2. Resultado estricto

- Archivo: `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_STRICT.md`
- Resultado: **18 PASS / 7 FAIL** (25 prompts)
- Raw output: `smoke_live_strict_raw.txt`

## 3. Comparación

- Cycle 5 harness laxo: **21 PASS / 0 FAIL**
- Strict harness: **18 PASS / 7 FAIL**

## 4. Lista de fallos reales restantes

- `S04` `sos iron man?` -> FAIL (sin oráculo estricto asignado en versión actual del runner).
- `S05` `cual es tu arquitectura?` -> FAIL (respuesta genérica sin señales estructurales suficientes).
- `S06` `puedes ver tu codigo?` -> FAIL (respuesta genérica/no accionable en capacidad local).
- `S07` `tengo miedo de que fracasemos con Carter` -> FAIL (sin oráculo estricto asignado).
- `S08` `Me llamo red` -> FAIL (guardado no confirmado).
- `S21` `pausala` -> FAIL (manejo de capability/media aún insuficiente para criterio estricto).
- `S23` `para cuando tengo una alarma?` -> FAIL (respuesta no cumple el estándar estricto de estado/capability).

## 5. Casos que antes eran PASS falso

Detectados como PASS laxo en Cycle 5 y FAIL en strict:

- `cual es tu arquitectura?`
- `puedes ver tu codigo?`
- `Me llamo red`

## 6. Casos realmente resueltos

Se mantienen PASS bajo criterio estricto:

- `lee PATH` + `Sí` (pending intent/follow-up funcional y honesto).
- Memoria recall: `Como me llamo?` y `Mi color favorito cual es?`.
- App flow básico: `abre/cierra notepad`, follow-ups asociados, `abre steam`/`abriste steam?`.
- Dependencia faltante de volumen (`pycaw`) reportada honestamente.
- Safety/messaging: rechazo ofensivo y guidance positivo sin claim de envío.

## 7. Veredicto

`STRICT_LIVE_TEXT_CORE_ALMOST_READY`

Razonamiento:

- strict smoke **no** pasa completo (7 FAIL);
- suite completa pasa (`441 passed`);
- `hardcode_guard` pasa (`clean`);
- `test_no_semantic_hardcodes` pasa (`16 passed`);
- no se detectan hardcodes nuevos en harness/runtime;
- persisten fallos estrictos en persona/capabilities, memoria write confirmation y algunos casos de capability missing.

## 8. Próximo paso

Antes de cualquier declaración `READY`:

1. Endurecer el propio strict harness para cubrir todos los prompts con oráculo explícito (sin `UNMAPPED`).
2. Luego sí abordar fixes de runtime para los FAIL reales restantes (persona/capabilities, memoria write confirmation, media/alarm follow-up), siempre sin hardcodes.
