# Round 9 - Refactor estructural dispatch + src

Modelo recomendado:

- Mejor: `GPT-5.2-Codex`
- Razonamiento: `High`
- Fallback: `Claude Opus 4.7`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Pagar la deuda estructural de tamano que deja la campana v2->v3 cerrada.
Esta ronda NO agrega features. Refactoriza responsabilidades para recuperar
margen de mantenibilidad.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md` (especialmente R-V3-C3 y R-P3-29)
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/response_composer.py`
- `Carter_v3/src/carter_v3/turn_support.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_9_LOG.md`

SITUACION ACTUAL
Al cierre de la campana v2->v3:
- `src/carter_v3/tools/dispatch.py` = 741 lineas (cap original: ~300).
- `src/carter_v3` total = 6239 lineas (cap documental original: 4500).
- `tests/` = 2317 lineas en 20 modulos.
- Catálogo publico = 32 tools (este cap SI se preserva).

MISION
Reducir tamano y claridad sin romper contratos ni tests.

OBJETIVOS CONCRETOS Y ORDENADOS
1. Partir `dispatch.py` en modulos cohesionados por familia de tool:
   - `tools/dispatch_system.py`    (system_set_volume, system_mute, system_get_*)
   - `tools/dispatch_app.py`       (app_open, app_close, process_list)
   - `tools/dispatch_window.py`    (window_list, window_focus, window_close)
   - `tools/dispatch_filesystem.py` (filesystem_*)
   - `tools/dispatch_web.py`       (web_open_url, web_search, web_extract)
   - `tools/dispatch_terminal.py`  (terminal_run_command)
   - `tools/dispatch_misc.py`      (clock_now, notify_toast, memory_*, gui_*, desktop_screenshot, heartbeat_status, network_*)
   - `tools/dispatch.py` se convierte en el router/aggregator que importa de los anteriores.
   El API publica de `ToolDispatcher` no cambia.

2. Solo si (1) queda limpio: evaluar si `verifier.py` (460 lineas)
   admite particion similar sin enredar dependencias circulares.
   No hacerlo si introduce complejidad nueva.

3. No tocar `agent.py`, `turn_support.py`, `response_composer.py` ni tests
   a menos que el refactor los rompa.

REGLAS
- Los tests actuales deben seguir pasando SIN CAMBIOS.
- El catalogo publico de 32 tools no cambia.
- Los contratos publicos (mission_status, VerifiedOutcome, etc.) no cambian.
- No se agrega ni elimina ninguna tool.
- hardcode_guard sigue clean.
- Si en algun punto el refactor introduce mas lineas de las que elimina,
  para y reporta sin seguir.

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_9_refactor_full --out audit/runs/round_9_refactor_full.json`

El global del runner no debe bajar vs el baseline de Round 7 (99.24%).

METRICAS A REPORTAR
- lineas antes/despues por archivo
- total `src/carter_v3` antes/despues
- tests antes/despues (debe ser el mismo numero)
- runner global antes/despues

ENTREGA
1. Que partiste, como y por que esa particion
2. Que NO tocaste y por que
3. Metricas reales
4. Regresiones (si las hay, honestamente)
5. Updates en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_9_LOG.md`
```
