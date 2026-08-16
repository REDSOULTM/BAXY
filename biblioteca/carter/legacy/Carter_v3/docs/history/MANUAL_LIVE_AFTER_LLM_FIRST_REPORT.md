# MANUAL_LIVE_AFTER_LLM_FIRST_REPORT

Fecha: 2026-05-05

## Veredicto

`MANUAL_LIVE_LLM_FIRST_READY`

El spotcheck manual-live posterior a LLM-first queda reparado en el smoke exacto equivalente. La suite completa, hardcode guard, tests anti-hardcode, tests LLM-first y smoke manual-live pasan.

## Qué se reparó

| Área | Fix | Evidencia |
|---|---|---|
| Memoria informal/identidad | `MemoryStore` y pending offers se pasan como locked facts al prompt/verbalizer. | `aaaa soy red?` conserva `red`; tests de memoria pasan. |
| Memoria duplicada | `memory_save` duplicate ahora es idempotente, no failed. | `Me llamo red` después de memoria existente queda `complete`. |
| Preferencias | Pending memory fact queda disponible para el siguiente turno. | `Mi color favorito cual es?` responde `rojo` en primer intento del smoke. |
| Hora | `What time it is?` entra a `clock_now`; `VerifierStatus.SKIPPED` read-only cuenta como evidencia. | `Que hora es?` y `What time it is?` usan `clock_now`. |
| Arquitectura | Prompt incluye stack real de Carter. | Test de persona/capability y smoke de arquitectura pasan. |
| Código/filesystem | Prompt aclara capacidad local con ruta/carpeta autorizada. | `puedes ver tu codigo?` no niega falsamente la capacidad. |
| Filesystem read | Scaffold universal de `filesystem_read_text` incluye contenido/snippet real. | Lectura de `ContextoCarter.md` produce respuesta útil. |
| Pending cleanup | No queda pending si la lectura devolvió texto útil. | `Sí` posterior no repite lectura resuelta. |
| Volumen/pycaw | Missing dependency queda como `needs_environment` y no success falso. | Ambos prompts de volumen reportan `pycaw`. |
| Alarmas | Sin tool verificable, no se afirma creación ni estado inventado. | Alarm create/query pasan sin fake success. |

## Archivos principales cambiados

- `src/carter_v3/agent.py`: LLM-first verbalization, memory facts, duplicate memory idempotent, filesystem pending cleanup.
- `src/carter_v3/turn_support.py`: facts de arquitectura/filesystem/memoria y guard read-only evidence.
- `src/carter_v3/response_composer.py`: scaffolds de filesystem read y memory duplicate.
- `src/carter_v3/request_patterns.py`: clock detector para English básico.
- `src/carter_v3/llm_verbalizer.py`: verbalizer LLM-first para chat/resultados.
- `audit/smoke_manual_equivalent.py`: secuencia exacta manual-live `18/18` y reporte automático.
- `tests/test_memory_runtime_consistency.py`: regresiones del spotcheck manual.

## Validación ejecutada

| Comando | Resultado |
|---|---|
| `python audit/hardcode_guard.py` | `hardcode_guard: clean (57 files scanned)` |
| `python -m pytest tests/test_no_semantic_hardcodes.py -v` | `17 passed` |
| `python -m pytest tests/test_llm_first_responses.py -v` | `10 passed` |
| `python -m pytest --tb=short` | `471 passed in 169.66s` |
| `python audit/smoke_manual_equivalent.py` | `manual_live_after_llm_first: 18/18 PASS` |

Resumen explícito requerido:

- suite completa: `471 passed`;
- hardcode_guard: `clean (57 files scanned)`;
- anti-hardcode: `17 passed`;
- LLM-first: `10 passed`;
- smoke manual-live: `18/18 PASS`.

## Smoke exacto manual-live

Reporte generado: `MANUAL_LIVE_AFTER_LLM_FIRST_SMOKE_RESULTS.md`.

Script generador reproducible: `audit/smoke_manual_equivalent.py`.

Comando exacto reproducible desde PowerShell:

`Set-Location "C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\Carter_v3"; C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe audit/smoke_manual_equivalent.py`

Secuencia validada:

1. `hola`
2. `aaaa soy red?`
3. `Que hora es?`
4. `What time it is?`
5. `Abre steam`
6. `pon el volumen del pc a 20`
7. `Quien sos?`
8. `Cual es tu arquitectura?`
9. `puedes ver tu codigo?`
10. `Me llamo red`
11. `Como me llamo?`
12. `Mi color favorito es rojo`
13. `Mi color favorito cual es?`
14. `lee C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\ContextoCarter.md que es?`
15. `Sí`
16. `pon volumen a 20`
17. `pon una alarma para hoy a las 9 am`
18. `para cuando tengo una alarma?`

Resultado: `18/18 PASS`.

## Hardcode status

- No se añadieron hardcodes semánticos por prompt.
- Los valores `red`/`rojo` solo aparecen en pruebas/smoke como datos de fixture, no como lógica runtime.
- `hardcode_guard.py` sigue limpio.
- No se relajó el guard anti-hardcode.

## Riesgos restantes

- El smoke manual-live usa adapter controlado para reproducir criterios exactos; conviene re-ejecutar live con el modelo local real antes de cerrar distribución final.
- La calidad estilística final sigue dependiendo del modelo local, aunque los facts/guards ahora restringen contradicciones y fake success.
- El emergency fallback determinístico sigue existiendo para LLM vacío/placeholder, como safety fallback, no como ruta normal.

## Cierre

No hay blockers abiertos para el alcance manual-live LLM-first actual. Si el live real con Ollama produce una variación nueva, debe tratarse como nuevo ciclo de spotcheck, no como reapertura de canned trivial responses.
