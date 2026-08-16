# V2 Import Round 9 - Refactor dispatch/src

Fecha: 2026-05-04.

## 1. Objetivo

Pagar deuda estructural en `tools/dispatch.py` sin cambiar catalogo, contratos ni tests.

## 2. Que cambie

- `tools/dispatch.py` se separa por familia en:
  `dispatch_system.py`, `dispatch_app.py`, `dispatch_window.py`,
  `dispatch_filesystem.py`, `dispatch_web.py`, `dispatch_terminal.py`,
  `dispatch_misc.py`.
- `ToolDispatcher` queda como router/aggregator via mixins, API publica intacta
  (monkeypatches a `_system_set_volume` y `_windows_shellexecute` siguen validos).
- `dispatch.py` reexporta `os`, `subprocess` y `webbrowser` para mantener
  compatibilidad con monkeypatches de tests.
- `window_close` no se agrega (no existe en el catalogo v3).
- `verifier.py` no se parte para evitar dependencias circulares.
- `agent.py`, `response_composer.py`, `turn_support.py` y tests no se tocan.

## 3. Metricas de tamano (lineas)

- `src/carter_v3/tools/dispatch.py`: `768 -> 75`
- `src/carter_v3/tools/dispatch_system.py`: `0 -> 82`
- `src/carter_v3/tools/dispatch_app.py`: `0 -> 148`
- `src/carter_v3/tools/dispatch_window.py`: `0 -> 87`
- `src/carter_v3/tools/dispatch_filesystem.py`: `0 -> 126`
- `src/carter_v3/tools/dispatch_web.py`: `0 -> 153`
- `src/carter_v3/tools/dispatch_terminal.py`: `0 -> 20`
- `src/carter_v3/tools/dispatch_misc.py`: `0 -> 74`
- `src/carter_v3` total: `6353 -> 6350`
- `tests/` total: `2468 -> 2468`
- Archivo mas grande ahora: `src/carter_v3/tools/verifier.py` (`536` lineas)

## 4. Validacion

- `python -m pytest -q` -> PASS.
- `python audit/hardcode_guard.py` -> `hardcode_guard: clean (54 files scanned)`.
- `python audit/full_matrix_runner.py --mode live-safe --label round_9_refactor_full --out audit/runs/round_9_refactor_full.json` ->
  `global=99.81% P1=100.0% P2=99.52% P3=100.0% cat11=100.0% cat18=100.0% p95=1231.5ms`.
  Un fallo en `C5.33` (cat5) por `active_app_policy` (active_app_contamination: "configuracion").

Baseline previo: Round 7 `global_pass_rate=99.24%`.

## 5. Regresiones

- Un fallo aislado en full_matrix (`C5.33`, cat5). Investigacion pendiente.
- Pytest y hardcode_guard sin regresiones.

## 6. Archivos tocados

- `src/carter_v3/tools/dispatch.py`
- `src/carter_v3/tools/dispatch_system.py`
- `src/carter_v3/tools/dispatch_app.py`
- `src/carter_v3/tools/dispatch_window.py`
- `src/carter_v3/tools/dispatch_filesystem.py`
- `src/carter_v3/tools/dispatch_web.py`
- `src/carter_v3/tools/dispatch_terminal.py`
- `src/carter_v3/tools/dispatch_misc.py`
- `CHANGELOG.md`
- `RESIDUAL.md`
- `V2_IMPORT_ROUND_9_LOG.md`
