# LLM_FIRST_RESPONSE_REPORT

Fecha: 2026-05-05

## 1. Respuestas canned eliminadas

- Eliminada la ruta `_local_short_reply()` en `src/carter_v3/agent.py`.
- Eliminados los finales hardcodeados normales para:
  - `Hola. ¿Qué necesitas?`
  - `Sí.`
  - `De nada.`
  - `Necesito un poco más de contexto.`
  - `Sigo aquí. Dime qué quieres hacer.`
  - `¿Puedes precisar a qué te refieres?`
- `compose_default_reply(...)` y demás composer quedan como scaffold/evidence guard, no como ruta normal final para tools/policy/capability.

## 2. Rutas que ahora llaman LLM

- `trivial_lowinfo` -> `generate_chat_reply(...)`, no tools.
- `ambiguous_short` -> `generate_chat_reply(...)`, no tools.
- `policy_block` -> `generate_result_reply(...)` con policy facts.
- `unsupported_visual` -> `generate_result_reply(...)` con capability/environment facts.
- `missing_capability` / resolver ambiguity -> `generate_result_reply(...)` con `needs_user` facts.
- `memory_offer` -> `generate_result_reply(...)`.
- `recent_action_status` -> `generate_result_reply(...)` con last tool/verifier facts.
- `tool_result` -> `generate_result_reply(...)` con tool results and verifier outcomes.
- identity/architecture/capability/knowledge simple mantienen la llamada LLM sin tools ya existente vía `build_messages(...)`.

## 3. Seguridad y fake-success

- `mission_status` y `termination_reason` se calculan antes de verbalizar resultados.
- El LLM recibe facts cerrados (`tool_calls`, `tool_results`, `verifier_outcomes`, `policy_blocks`, `engine_errors`).
- El LLM no ejecuta tools, no modifica memoria y no decide status.
- Si status no es complete, el prompt prohíbe claims globales de completion.
- Los guards post-reply siguen activos; si un LLM dice `Completado.` en una acción unverified, la respuesta se reemplaza por fallback honesto.

## 4. Latencia

- Trivial/direct chat sigue como no-tools.
- No hay screenshots, UIA, app resolver ni tool dispatch para saludos/ok/gracias.
- `generate_chat_reply(...)` usa prompt corto y `max_short=True`.
- Se usa el mismo adapter precargado; no hay segundo modelo.

## 5. Tests agregados/cambiados

- Agregado `src/carter_v3/llm_verbalizer.py`.
- Actualizado `src/carter_v3/agent.py` para pasar rutas normales por verbalizer.
- Actualizado `src/carter_v3/adapters/scripted_adapter.py` para no consumir colas normales en llamadas de verbalizer de tests.
- Endurecido `audit/hardcode_guard.py` con `canned_trivial_reply_literal`.
- Agregado `tests/test_llm_first_responses.py` (10 tests).
- Actualizado `tests/test_no_semantic_hardcodes.py` (17 tests total).
- Actualizado `tests/test_agent_integration.py` para el criterio LLM-first de saludo.
- Creado `audit/smoke_manual_equivalent.py`.
- Generado `MANUAL_EQUIVALENT_SMOKE_RESULTS.md`.

## 6. Suite completa

Comando:

- `python -m pytest --tb=short`

Resultado final actualizado tras el ciclo manual-live posterior:

- `471 passed in 177.87s`

## 7. hardcode_guard

Comando:

- `python audit/hardcode_guard.py`

Resultado final:

- `hardcode_guard: clean (57 files scanned)`

Comando anti-hardcode específico:

- `python -m pytest tests/test_no_semantic_hardcodes.py -v`

Resultado:

- `17 passed`

## 8. LLM-first focused tests

Comando:

- `python -m pytest tests/test_llm_first_responses.py -v`

Resultado:

- `10 passed`

Cobertura clave:

- `Hola`, `HGOla`, `ok`, `gracias`: no tools + LLM call.
- `Hola` cambia si cambia el mock LLM.
- Identity/architecture/capability reciben contexto Carter y `TOOL_CATALOG`.
- Memory recall usa LLM para redactar facts reales.
- Tool result unverified llama LLM pero no puede quedar como completed.

## 9. Smoke manual-equivalent

Comando:

- `python audit/smoke_manual_equivalent.py`

Resultado actualizado:

- `manual_live_after_llm_first: 18/18 PASS`
- Reporte: `MANUAL_LIVE_AFTER_LLM_FIRST_SMOKE_RESULTS.md`

Casos cubiertos:

- `Hola` LLM, no canned.
- identidad informal con memoria (`aaaa soy red?`).
- hora en español y English básico (`What time it is?`).
- app open con verificación.
- `Quien sos?` identidad Carter local.
- `Cual es tu arquitectura?` stack real.
- `puedes ver tu codigo?` no niega filesystem.
- memory write/recall consistente.
- filesystem read con respuesta útil y limpieza de pending follow-up.
- duplicate memory write idempotente.
- preference recall al primer intento.
- pycaw missing honesto.
- alarm missing honesto.

## 10. Riesgos restantes

- El emergency fallback estructural todavía existe para casos donde el LLM devuelve vacío/placeholder/`OK.`; se mantiene por seguridad, no como ruta normal.
- `response_composer.py` conserva templates como scaffolds internos; deben seguir sin convertirse en respuesta final normal.
- El smoke manual-equivalent usa adapter mock; el live strict histórico debe re-ejecutarse aparte si se quiere medir variabilidad real de Ollama.
- La calidad final sigue dependiendo del modelo local; los guards mitigan fake success pero no garantizan estilo perfecto.

## 11. Veredicto

`LLM_FIRST_READY` queda supersedido por `MANUAL_LIVE_LLM_FIRST_READY` en `MANUAL_LIVE_AFTER_LLM_FIRST_REPORT.md`.

Criterio cumplido:

- texto visible normal pasa por LLM en rutas modificadas;
- trivial no usa tools pero sí LLM;
- respuestas canned triviales eliminadas del runtime normal;
- suite completa pasa;
- hardcode_guard pasa;
- no fake success en test unverified;
- manual-equivalent pasa.
