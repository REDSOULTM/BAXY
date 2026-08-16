# V2 -> V3 Import Round 2 - Live Log

> Trazabilidad incremental de la ronda. Cada step se marca cuando termina,
> con archivos tocados y resultado de validacion.

Date: 2026-05-03
Author: GPT-5.2-Codex

## Plan

1. Portar cierre cooperativo de apps (WM_CLOSE -> terminate -> taskkill).
2. Mejorar inventario de procesos/ventanas y foco de ventana real.
3. Reforzar verificacion y follow-ups deicticos basados en targets observados.
4. Tests y validacion obligatoria.

---

## Steps

### STEP 0 - log creado [DONE]

Archivo: `V2_IMPORT_ROUND_2_LOG.md`.

### STEP 1 - Cierre cooperativo + inventario window/process [DONE]

**Imports selectivos desde v2:**
- `legacy/Carter_v2/src/carter_v2/capabilities/_graceful_close.py` -> nueva utilidad
  `src/carter_v3/tools/graceful_close.py` (ladder WM_CLOSE -> terminate -> taskkill).
- `legacy/Carter_v2/src/carter_v2/capabilities/process.py::_list_processes` ->
  detalle de procesos con pid/mem/cpu en `process_list`.
- `legacy/Carter_v2/src/carter_v2/capabilities/window.py` -> patrones win32
  para focus y enumeracion de ventanas.

**Files touched:**
- `src/carter_v3/tools/graceful_close.py` (NEW)
- `src/carter_v3/tools/dispatch.py`
- `src/carter_v3/perception/probe.py`

**Behavior changes:**
- `app_close` ahora usa cierre cooperativo (WM_CLOSE -> terminate -> taskkill por PID).
- `window_focus` ahora ejecuta focus real en Windows (no stub).
- `process_list` incluye `processes` con `pid`, `memory_mb`, `cpu_percent`.
- `window_list` incluye `windows` con `title`, `pid`, `process_name`.
- `WindowProbe` expone `windows()` y `active_window()` con pid + proceso.

### STEP 2 - Verificacion y deicticos observados [DONE]

**Imports selectivos desde v2:**
- Verificacion estructural de ventanas/procesos (readback real post-action).

**Files touched:**
- `src/carter_v3/tools/verifier.py`
- `src/carter_v3/session_state.py`
- `src/carter_v3/agent.py`

**Behavior changes:**
- `window_focus` se verifica contra el titulo activo real (pending si no match).
- `app_close` verifica ausencia de proceso *y* ventana.
- Follow-ups deicticos ahora pueden usar el ultimo target observado por
  `window_list` (active_window / active_app / foreground_process).

### STEP 3 - Tests nuevos [DONE]

**Files added:**
- `tests/test_graceful_close.py`
- `tests/test_verifier_actions.py`

**Files touched:**
- `tests/test_agent_integration.py`

### STEP 4 - Validacion obligatoria [DONE]

- `python -m pytest -q`: PASS
- `python audit/hardcode_guard.py`: clean (43 files scanned)
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_2_full --out audit/runs/v2_import_round_2_full.json`
  - global=99.05% P1=100.0% P2=98.19% P3=100.0%
  - cat11=100.0% cat18=100.0% p95=1785.8ms
  - fails: C14.01, C14.02, C14.03, C14.04, C14.09
- `python audit/full_matrix_runner.py --mode live-safe --category 7 --label v2_import_round_2_cat7 --out audit/runs/v2_import_round_2_cat7.json`
  - global=100.0% P1=0.0% P2=16.67% P3=0.0% p95=58.7ms
- `python audit/full_matrix_runner.py --mode live-safe --category 13 --label v2_import_round_2_cat13 --out audit/runs/v2_import_round_2_cat13.json`
  - global=100.0% P1=0.0% P2=0.0% P3=33.33% p95=401.8ms

---

## Descartes explicitos (round 2)

- `uninstall_app` (winget/registry) por riesgo y superficie.
- SystemProbe completo (registro + WMI) por overhead y contaminacion.
- Window/UIA actions avanzadas (minimize/maximize/resize/etc.) por scope.
- hacks por marca o alias por app.
