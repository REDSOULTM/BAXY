# FULL_CLOSURE_BASELINE

Fecha: 2026-05-06

## Fuente de verdad leída

- `../ContextoCarter.md`: leído completo. Mandato principal: Carter debe ser local-first, privado, rápido, honesto, verificable, universal, sin fake success, sin hardcodes por app/frase, sin acciones destructivas reales y sin afirmar éxito sin evidencia.
- `Carter_v3/ContextoCarter.md`: no existe en este workspace.
- `pyproject.toml`: paquete `carter_v3`, Python >=3.10, deps base `psutil`, `requests`, `PyYAML`; opcionales `fuzzy`, `audio`, `ui`, `test`.
- Reportes previos leídos: `TRUE_CARTER_V3_TEXT_CORE_READY_REPORT.md`, `TEST_TRUE_READY_REPORT.md`, `FINAL_TEST_DIFF_AUDIT.md`, `TEST_FAILURE_AUDIT.md`.
- Memoria repo consultada: `true_ready_round_gpt55.md`, `full_live_llm_matrix.md`, `live_safe_runtime_repair_v2.md`.

## Git baseline

Comando ejecutado:

`git status; git log --oneline -10; git diff --stat`

Estado:

- Rama: `repo-cleanup-test-rebuild`.
- HEAD: `d8469442 Validate Carter v3 test to true ready without hardcodes`.
- Tag en HEAD: `carter-v3-text-core-full-654-ready`.
- Working tree: sucio antes de esta auditoría.

Cambios no staged detectados al inicio:

- `src/carter_v3/agent.py`
- `src/carter_v3/llm_verbalizer.py`
- `src/carter_v3/response_composer.py`
- `src/carter_v3/session_state.py`
- `src/carter_v3/tools/verifier.py`
- `src/carter_v3/turn_support.py`

Diff stat inicial:

- 6 files changed, 95 insertions(+), 17 deletions(-).

Resumen del diff inicial preexistente:

- `agent.py`: endurece launch directo verificando paths/`PATH`, agrega clock-time action shape, cambia respuesta missing capability, bypass parcial de verbalizer para herramientas estructurales, cambia app_close record solo si confirmado.
- `llm_verbalizer.py`: soporta formatos alternativos de prior turns y añade restricciones contra workarounds por terminal/programas externos cuando falta capability.
- `response_composer.py`: app_close con `already_absent` ya no afirma cierre.
- `session_state.py`: usa `display_name` como target reciente cuando existe.
- `tools/verifier.py`: app_close `already_absent` pasa de confirmado a pending; reubica `_find_window_any`.
- `turn_support.py`: refuerza prompt contra workarounds externos y soporta prior_turns `{user, assistant}`.

## Últimos commits

- `d8469442` Validate Carter v3 test to true ready without hardcodes
- `45e7d798` Stabilize Carter v3 text core with live minimum 36 ready
- `b4f80788` Implement LLM-first responses and manual live validation
- `8f3adefc` Resolve Carter v3 strict live runtime blockers cycle 7
- `3a7aa176` Checkpoint before GPT55 cycle 7 strict blockers
- `76c10510` Close Carter v3 live runtime cycle 5
- `dcf2d956` Fix pending intent live smoke encoding root cause
- `db768b7e` Clean semantic hardcodes and harden guard
- `6aae2b0a` Repair Carter v3 runtime without semantic hardcodes (V2)
- `4d9c9f2f` Checkpoint before live runtime repair

## Tests/runners disponibles

- Unit/integration pytest: 32 archivos `tests/*.py`, 478 tests recolectados en baseline.
- `audit/hardcode_guard.py`.
- `audit/minimum_testing_runner.py`: 36 casos, 18 categorías x 2.
- `audit/full_matrix_runner.py`: 654 casos importados desde `legacy/Carter_v2/audit/runners/full_live_llm_cases.py`.
- Smoke/manual runners: `smoke_manual_equivalent.py`, `smoke_live_strict.py`, `smoke_live_post_cleanup.py`, `smoke_live_cycle_3.py`, `smoke_live_cycle_5.py`.
- No existe `audit/category_30_runner.py`; el set de 30+ por categoría ya existe como `full_matrix_runner.py` + `full_live_llm_cases.py` legado.

## Capacidades actuales detectadas

- Conversación, identidad, conocimiento general sin tools.
- Memoria local: save/recall/delete con SQLite `MemoryStore`.
- Sistema read-only: hora, volumen, batería, CPU, RAM, GPU, IP, procesos, ventanas.
- Audio: set volume / mute con `pycaw` si disponible y verificación.
- Apps/ventanas: open/close/focus con resolver, proceso/ventana/UIA best effort y causal baseline para open.
- Filesystem: list/read/write/search/delete con policy/verifier y recursos controlados.
- Web: open/search/extract con verificación de browser/backend.
- Terminal: command runner con policy y verifier de exit code.
- Percepción: screenshot/window/process/UIA; sin VLM/OCR pesado como capability completa.
- GUI: click/type expuestos como último recurso, stubs/no autoaprobación alta.

## Capacidades faltantes o frágiles

- Alarmas/recordatorios: no hay herramienta real de create/list/cancel/get/cleanup. La suite previa solo validaba missing capability honesto.
- Calendar/time future effects: no hay scheduler/verificador local dedicado.
- Messaging draft/send: fuera de scope o debe ser draft/permission-gated; no capability real actual.
- Browser GUI avanzado: no click/scroll/tab control verificado real; web open/search/extract es mínimo.
- `app_close already_absent`: el diff inicial alinea con ContextoCarter (no afirmar cierre), pero rompe un test heredado.
- LLM-first: el diff inicial salta verbalizer en app tools estructurales y rompe `test_llm_first_responses.py`.

## Baseline de comandos ejecutados

### Pytest completo

Comando:

`$env:PYTHONPATH='src'; C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m pytest --tb=short`

Resultado:

- 476 passed
- 2 failed
- Duración: 137.87s

Fallas:

1. `tests/test_llm_first_responses.py::test_tool_result_unverified_calls_llm_but_cannot_be_completed`
   - Esperado: `adapter.verbalizer_calls == 1`.
   - Actual: `0`.
   - Causa probable: bypass preexistente `_should_keep_structural_tool_reply()` evita verbalizer en `app_open` aun cuando el resultado es `UNVERIFIED`.
2. `tests/test_verifier_actions.py::test_app_close_confirmed_when_already_absent`
   - Esperado heredado: `confirmed`.
   - Actual: `pending`.
   - Causa: diff preexistente evita fake success cuando no hubo cierre real. Esta expectativa de test contradice el nuevo criterio del prompt: `app_close` absent debe quedar unverified/pending, no complete.

### Hardcode/semantic/LLM-first gates

Comando:

`C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe audit/hardcode_guard.py`

Resultado:

- `hardcode_guard: clean (57 files scanned)`.

Comando:

`C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m pytest tests/test_no_semantic_hardcodes.py -v`

Resultado:

- 17 passed.

Comando:

`C:/Users/usuario/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m pytest tests/test_llm_first_responses.py -v`

Resultado:

- 11 passed
- 1 failed: misma falla LLM-first por bypass de verbalizer.

## Riesgos

- Hay cambios preexistentes no commiteados; cualquier implementación debe preservarlos o corregirlos explícitamente.
- El repo está en estado `NOT READY` por 2 fallas de pytest.
- Implementar alarmas con routing por palabras sería una violación de anti-hardcode; debe depender de catálogo/LLM/tool schema y parser temporal estructural, no `looks_alarm_request`.
- El catálogo tiene cap público `<=32`; una capacidad nueva debe conservar el cap o justificar formalmente elevarlo. Preferible: una herramienta compuesta `local_reminder` en lugar de 4-5 herramientas separadas.
- Live runners requieren Ollama en `127.0.0.1:11434`; si no está disponible, será BLOCKER_REAL externo documentable.

## Baseline verdict

`CARTER_V3_FULL_NOT_READY_BASELINE`

Razones:

- pytest completo falla 2/478.
- `LLM-first` no se mantiene en una ruta unverified.
- Alarmas/recordatorios legítimos aún no están implementados como capability local verificable; solo existe rechazo honesto.
