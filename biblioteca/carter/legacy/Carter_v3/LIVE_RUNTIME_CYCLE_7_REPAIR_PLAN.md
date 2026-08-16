# LIVE_RUNTIME_CYCLE_7_REPAIR_PLAN

Fecha: 2026-05-05

Fuente: `LIVE_RUNTIME_CYCLE_7_BLOCKERS_AUDIT.md` + `ContextoCarter.md`.

Objetivo: cerrar únicamente S06/S21/S22/S23 sin abrir frentes nuevos, sin hardcodes por frase/app/marca y sin relajar smoke.

## Cambio 1 — Prompt universal de capability honesty desde catálogo

- Archivo: `src/carter_v3/turn_support.py`.
- Casos cubiertos: S06, S22, S23.
- Qué cambiar:
  - Reforzar que las preguntas sobre capacidades deben responderse según `TOOL_CATALOG`.
  - Si existe una tool relacionada, Carter no debe negar capacidad absoluta: debe explicar qué puede hacer con herramientas locales y qué input/evidencia falta.
  - Si la acción requiere un efecto futuro/externalizado o una capability no listada, Carter debe decir que no tiene capacidad verificable en el catálogo y no prometer chequeos/creación/estado.
  - Carter no debe sugerir apps concretas no aportadas por usuario o evidencia.
- Por qué es universal:
  - Opera sobre catálogo/evidencia, no sobre prompts S06/S22/S23.
  - No menciona alarmas, media, marcas ni frases de smoke.
- Por qué NO es hardcode:
  - No inspecciona `user_text` con tokens concretos.
  - No crea respuestas literales para un caso.
- Tests:
  - `tests/test_runtime_persona_and_capabilities.py` para verificar contrato de no negar filesystem local, no prometer capabilities ausentes, no inventar estado futuro sin tool.
- Smoke cases:
  - S06, S22, S23.
- Rollback:
  - Revertir solo el bloque nuevo de `build_messages`.

## Cambio 2 — Fallback universal de capability missing para acciones ambiguas sin tool

- Archivo: `src/carter_v3/response_composer.py` y uso mínimo en `src/carter_v3/agent.py`.
- Casos cubiertos: S21 y otros deícticos/acciones sin objetivo/capability verificable.
- Qué cambiar:
  - Crear `compose_missing_capability_reply()` con wording genérico: falta una capacidad verificable en el catálogo o un objetivo/evidencia concreta; no se ejecutó nada.
  - Usarlo en ramas ya existentes de acción sin tool/objetivo claro, sin añadir detectores semánticos.
- Por qué es universal:
  - Se activa por estado estructural existente: `looks_action`, ausencia de `executed_calls`, ausencia de resolver/objetivo seguro.
- Por qué NO es hardcode:
  - No menciona media, alarma, marcas ni prompts.
  - No mira `user_text` con palabras concretas.
- Tests:
  - `tests/test_live_regressions_from_user_log.py` y `tests/test_runtime_no_fake_success_live_cases.py` validan que capability missing produce respuesta honesta.
- Smoke cases:
  - S21.
- Rollback:
  - Volver a `compose_missing_target_reply()` en esas ramas y eliminar helper.

## Cambio 3 — Guard estructural contra promesas sin herramienta/evidencia

- Archivo: `src/carter_v3/guards.py` con ajuste mínimo en tests.
- Casos cubiertos: S23 y clase general de promesas futuras/chequeos sin tool.
- Qué cambiar:
  - Extender `fake_success_guard` con una señal estructural conservadora: si no hay verificación confirmada y el reply contiene una mención horaria junto con una promesa de chequeo/acción futura en primera persona, debe bloquearse.
  - Mantener el fallback existente; no se debe convertir en routing por intención.
- Por qué es universal:
  - Opera sobre reply sin evidencia, no sobre el texto del usuario.
  - Captura una clase de fake-success risk: prometer acciones futuras/chequeos con hora sin herramienta confirmada.
- Por qué NO es hardcode:
  - No contiene marcas/apps ni ramas por prompts.
  - Usa forma temporal + promesa no verificada, igual que el guard actual ya bloquea claims “done” sin evidencia.
- Tests:
  - `tests/test_runtime_no_fake_success_live_cases.py` amplia cobertura del guard.
- Smoke cases:
  - S23.
- Rollback:
  - Revertir solo la condición nueva en `fake_success_guard`.

## Validación tras cada cambio

Después de cada cambio:

1. `python audit/hardcode_guard.py`
2. `python -m pytest tests/test_no_semantic_hardcodes.py -v`
3. Subset relevante del cambio.

Si `hardcode_guard` falla, revertir inmediatamente y documentar.
