# Round 2 - process / probe / window

Modelo recomendado:

- Mejor: `GPT-5.2-Codex`
- Razonamiento: `High`
- Fallback si se enreda: `GPT-5.1-Codex-Max`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

Puedes leer fuera de `Carter_v3/` unicamente:
- `ContextoCarter.md`
- `legacy/Carter_v2/**`

OBJETIVO DE ESTA RONDA
Ejecutar `V2 Import Round 2`: fortalecer la capa universal de procesos,
apps, ventanas y probes usando extraccion selectiva desde:
- `legacy/Carter_v2/src/carter_v2/capabilities/process.py`
- `legacy/Carter_v2/src/carter_v2/capabilities/probe.py`
- `legacy/Carter_v2/src/carter_v2/capabilities/window.py`

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/V2_IMPORT_ROUND_1_LOG.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/perception/probe.py`
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`
- `Carter_v3/src/carter_v3/resolvers/resource_resolver.py`
- `Carter_v3/src/carter_v3/tools/catalog.py`

TRAZABILIDAD OBLIGATORIA
Crea y actualiza:
- `Carter_v3/V2_IMPORT_ROUND_2_LOG.md`

SCOPE EXACTO
Si puedes importar/redisenar:
1. mejor `app_open`
2. mejor `app_close` / `process_stop_app`
3. mejor inventario de procesos/ventanas
4. mejor readback de ventana activa / foreground process
5. mejor resolucion universal app/window/process
6. cierre/focus/found-state mas verificable

No puedes importar raw:
- `steam_*`
- `office_*`
- uninstall
- CDP/browser
- hacks por marca
- aliases por app
- cualquier catalogo inflado

OBJETIVOS CONCRETOS
1. Mejorar close/focus con capa universal de window/process.
2. Reforzar probes baratos antes de GUI/vision.
3. Reusar `app_resolver` de Round 1, sin volverlo default-host-contaminating.
4. Aumentar cobertura real de:
   - categoria 7
   - partes baratas de categoria 13
   - follow-ups deicticos que dependan de targets verificados
5. Mantener `app_discovery` opt-in.

VALIDACION OBLIGATORIA
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_2_full --out audit/runs/v2_import_round_2_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 7 --label v2_import_round_2_cat7 --out audit/runs/v2_import_round_2_cat7.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 13 --label v2_import_round_2_cat13 --out audit/runs/v2_import_round_2_cat13.json`

INVARIANTES
- `mission_status` no cambia
- `VerifiedOutcome.status` no cambia
- `compute_mission_status()` sigue estructural
- respuestas post-tool salen de evidencia
- no fake success
- no active-app contamination en rutas no-accion
- no catalogo > 32
- no `if model_name == ...`
- no hardcodes por app

ENTREGA FINAL
1. Archivos modificados
2. Que importaste realmente de v2
3. Que descartaste y por que
4. Impacto real en categorias 7/13
5. Resultados reales de validacion
6. Riesgos abiertos
7. Cambios honestos en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_2_LOG.md`
8. Confirmacion de aislamiento
```

## Ejecucion real (2026-05-03)

Hecho en Round 2 (resumen):
- `app_close` ahora usa cierre cooperativo (WM_CLOSE -> terminate -> taskkill).
- `window_focus` ahora ejecuta focus real en Windows y verificacion best-effort.
- `process_list` devuelve inventario con pid/mem/cpu; `window_list` devuelve titulo/pid/proceso.
- Probes enriquecidos (`WindowProbe.windows()` y `active_window()`), con foreground proceso/titulo.
- Follow-ups deicticos pueden reutilizar target observado por `window_list`.
- Catalogo publico sin cambios; `app_discovery` sigue opt-in.

Archivos tocados:
- `src/carter_v3/tools/graceful_close.py` (nuevo)
- `src/carter_v3/tools/dispatch.py`
- `src/carter_v3/tools/verifier.py`
- `src/carter_v3/perception/probe.py`
- `src/carter_v3/agent.py`
- `src/carter_v3/session_state.py`
- `tests/test_graceful_close.py` (nuevo)
- `tests/test_verifier_actions.py` (nuevo)
- `tests/test_agent_integration.py`
- `tests/test_verifier.py`
- `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_2_LOG.md`

Importado selectivamente de v2:
- `_graceful_close.py` (ladder de cierre cooperativo).
- `process.py::_list_processes` (detalle de procesos).
- patrones win32 de `window.py` (focus/enumeracion basica).

Descartado explicitamente:
- `uninstall_app` (winget/registry) por riesgo/superficie.
- SystemProbe completo (registro/WMI) por overhead y contaminacion.
- acciones UIA avanzadas (min/max/resize/etc.) fuera de scope.
- hacks por marca / aliases por app.

Validacion real:
- `pytest -q`: PASS
- `audit/hardcode_guard.py`: clean (43 files scanned)
- `full_matrix_runner live-safe full`: global 99.05%, P1 100.0%, P2 98.19%, P3 100.0%, p95 1785.8ms
   - fails: C14.01, C14.02, C14.03, C14.04, C14.09
- `cat7 live-safe`: global 100.0% (P2 16.67%)
- `cat13 live-safe`: global 100.0% (P3 33.33%)

## Riesgos abiertos (para auditoria final)

1. Fallos C14.01/02/03/04/09 en full live-safe (ver `audit/runs/v2_import_round_2_full.json`).
2. `window_focus` sigue best-effort: algunas apps bloquean focus o cambian el titulo rapido; verificacion puede quedar pending/unverifiable.
