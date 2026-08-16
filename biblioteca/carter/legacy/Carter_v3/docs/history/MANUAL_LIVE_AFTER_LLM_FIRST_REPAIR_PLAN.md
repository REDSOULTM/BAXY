# MANUAL_LIVE_AFTER_LLM_FIRST_REPAIR_PLAN

Fecha: 2026-05-05

Objetivo: reparar el spotcheck manual posterior a LLM-first sin volver a respuestas enlatadas ni añadir hacks semánticos por transcript.

## Límites

- Máximo 5 cambios de código agrupados.
- Toda respuesta visible normal sigue siendo redactada por LLM/verbalizer.
- El runtime determinístico puede decidir tools, estado, policy, evidencia y memoria, pero no escribir conversación normal como sustituto de LLM.
- No codificar valores concretos del spotcheck (`red`, `rojo`, rutas específicas) fuera de pruebas/smoke.
- No relajar `audit/hardcode_guard.py` ni `tests/test_no_semantic_hardcodes.py`.

## Cambios planificados/aplicados

### 1. Memoria real como facts bloqueados

Archivos: `src/carter_v3/agent.py`, `src/carter_v3/turn_support.py`, `src/carter_v3/response_composer.py`.

- Pasar snapshot de `MemoryStore` y pending memory offers al prompt directo/verbalizer.
- Tratar `memory_save` duplicado como éxito idempotente.
- Verbalizar duplicados como dato ya registrado, no como fallo.

Valida:
- `aaaa soy red?`
- `Me llamo red`
- `Como me llamo?`
- `Mi color favorito es rojo` / `Mi color favorito cual es?`

### 2. Facts de arquitectura y filesystem local

Archivo: `src/carter_v3/turn_support.py`.

- Incluir contrato de arquitectura real: núcleo de texto, local model adapter, local LLM/Ollama, tools, policy, verifier, memory, composer/verbalizer, perception router y `mission_status`.
- Incluir contrato de alcance local: Carter puede inspeccionar archivos/código con ruta o carpeta autorizada, y no debe negar esa capacidad si el catálogo la tiene.

Valida:
- `Quien sos?`
- `Cual es tu arquitectura?`
- `puedes ver tu codigo?`

### 3. Hora/read-only evidence

Archivos: `src/carter_v3/request_patterns.py`, `src/carter_v3/turn_support.py`.

- Ampliar detector estructural de hora a English básico `What time it is?`.
- Considerar `VerifierStatus.SKIPPED` como evidencia válida para tools read-only/sincrónicas como `clock_now`; evita fallback falso de “no pude verificar”.

Valida:
- `Que hora es?`
- `What time it is?`

### 4. Filesystem read + pending cleanup

Archivos: `src/carter_v3/response_composer.py`, `src/carter_v3/agent.py`.

- Scaffold factual universal para `filesystem_read_text` con path y snippet del contenido real.
- No dejar pending follow-up si la lectura devolvió texto útil.

Valida:
- `lee ...ContextoCarter.md que es?`
- `Sí` inmediatamente después.

### 5. Estado honesto para dependencias/capabilities ausentes

Archivos: `src/carter_v3/agent.py`, `src/carter_v3/llm_verbalizer.py`, pruebas.

- Preservar `missing_dependency:pycaw` como `needs_environment`, sin éxito falso.
- No afirmar creación/estado de alarmas sin tool catalogada/evidencia.
- Mantener guard contra claims de completado cuando `mission_status` no es `complete`.

Valida:
- `pon el volumen del pc a 20`
- `pon volumen a 20`
- `pon una alarma para hoy a las 9 am`
- `para cuando tengo una alarma?`

## Validación requerida

1. `python audit/hardcode_guard.py`
2. `python -m pytest tests/test_no_semantic_hardcodes.py -v`
3. `python -m pytest tests/test_llm_first_responses.py -v`
4. `python -m pytest --tb=short`
5. `python audit/smoke_manual_equivalent.py`

## Criterio de salida

Declarar listo solo si:

- Full suite pasa.
- Hardcode guard pasa.
- Tests LLM-first pasan.
- Smoke exacto manual-live pasa `18/18`.
- No hay blocker nuevo de user-visible final text enlatado.
