# Round 14 - minimum live-safe / follow-ups / REPL routing

Fecha: 2026-05-04.

## Objetivo

Cerrar la regresion de `tool_policy` y de routing estructural que seguia
apareciendo en:

- `audit/minimum_testing_runner.py --mode live-safe`
- el REPL real de `Run_Carterv3.py`

sin meter hardcodes por app/modelo ni debilitar policy global.

## Cambios aplicados

- `request_patterns.py`
  - memoria de nombre (`user.name`);
  - volumen con nivel explicito;
  - reopen de objetivo recien cerrado;
  - `app_open` estructural para pedidos directos de abrir app;
  - mejor trimming de targets en compuestos.

- `agent.py`
  - filtro de `tool_call` por forma estructural del pedido;
  - respuestas cortas locales en espanol para inputs triviales;
  - registro de cierres recientes;
  - allowlist puntual para `memory_recall` en el guard de historial.

- `session_state.py`
  - follow-up fuerte vs deictico ambiguo.

- `turn_support.py`
  - priorizacion de terminal, volumen, memoria y cierre web/tab.

- `response_composer.py`
  - replies con evidencia para `memory_recall`, `system_set_volume`,
    `system_get_volume` y `terminal_run_command`.

- `launcher.py`
  - `app_discovery=True` en el REPL real.

- `minimum_testing_runner.py`
  - `cat11` bloqueado por seguridad no penaliza `required100`;
  - `auto_approve_high` queda en el harness minimo.

- `full_matrix_runner.py`
  - el builder compartido deja de autoaprobar `HIGH` por defecto.

## Validacion real

- `python -m pytest -q` -> PASS (`338` tests).
- `python audit/hardcode_guard.py` ->
  `hardcode_guard: clean (54 files scanned)`.
- `python audit/minimum_testing_runner.py --mode live-safe --label codex_finish_minimum_v5 --out audit/runs/codex_finish_minimum_v5.json`
  - `global=100.0%`
  - `required100=True`
  - `p95=8653.3ms`
  - `verdict=MINIMUM_TESTING_PASS_WITH_WARNINGS`

## Lectura honesta

- el minimo queda funcionalmente cerrado;
- el `PASS_WITH_WARNINGS` viene de `cat11` bloqueado por diseno en
  `live-safe`, no de una falla del core;
- no se cierra aqui la limitacion de crear PowerPoints ni las fallas de
  launch/verificacion dependientes del host real para apps externas.
