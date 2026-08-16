# FULL_CLOSURE_CYCLE_1_REPORT

Fecha: 2026-05-06

## Fallos iniciales

Comando baseline:

`$env:PYTHONPATH='src'; C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m pytest --tb=short`

Resultado inicial:

- 476 passed
- 2 failed

Fallas:

1. `tests/test_llm_first_responses.py::test_tool_result_unverified_calls_llm_but_cannot_be_completed`
   - `adapter.verbalizer_calls` era `0`, esperado `1`.
2. `tests/test_verifier_actions.py::test_app_close_confirmed_when_already_absent`
   - `app_close` con `already_absent` devolvía `pending`, test heredado esperaba `confirmed`.

## Causa real

1. El diff preexistente agregó `_should_keep_structural_tool_reply()` para todos los `app_open`, `app_close` y `window_focus`. Eso saltaba el verbalizer en casos unverified y rompía LLM-first.
2. El cambio de verifier para `already_absent` es correcto según ContextoCarter y el prompt actual: si no había proceso/ventana, Carter no cerró nada y no debe marcar `complete`. El test heredado validaba fake success.

## Cambios hechos

1. `agent.py`: `_should_keep_structural_tool_reply()` ahora solo conserva reply estructural para `app_close` con `data['already_absent']`; no salta LLM-first para `app_open`/`window_focus`/otros app tools.
2. `tests/test_verifier_actions.py`: el caso `already_absent` ahora espera `VerifierStatus.PENDING` y evidencia `already_absent=True`.

## Por qué no son hardcodes

- No se comparan prompts exactos.
- No se agrega app/brand/frase/ruta.
- La condición usa evidencia estructural del tool result (`already_absent`) y tipo de tool, no texto del usuario.
- El test se ajusta a una regla universal de verificación: ausencia previa no equivale a cierre confirmado.

## Tests ejecutados

Enfocados:

`$env:PYTHONPATH='src'; C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m pytest tests/test_llm_first_responses.py::test_tool_result_unverified_calls_llm_but_cannot_be_completed tests/test_verifier_actions.py::test_app_close_pending_when_already_absent --tb=short -q`

Resultado:

- 2 passed.

Suite completa:

`$env:PYTHONPATH='src'; C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m pytest --tb=short`

Resultado:

- 478 passed.
- Duración: 136.61s.

## Estado tras ciclo

`CYCLE_1_BASELINE_REPAIRED`

Queda pendiente: ALARMS_REMINDERS local real y revalidaciones completas finales.
