# SECOND PASS TEXT CORE HARDENING REPORT

## Que se arreglo

### 1) Bug real en resolver/verificacion de `app_open`

- **Archivo:** `src/carter_v3/tools/dispatch_app.py`
- **Fix:** corregida indentacion en `_matching_process_names`.
- **Impacto:** vuelve a calcular correctamente `bare` y matching exact/partial case-insensitive, mejorando baseline de procesos para verificacion causal.

### 2) Estado terminal honesto para misiones parciales

- **Archivos:** `src/carter_v3/trace.py`, `src/carter_v3/agent.py`
- **Fixes:**
  - agregado estado canonico `PARTIAL_WITH_NEXT_STEP` en `TURN_STATES`;
  - mapeo `MissionStatus.PARTIAL -> PARTIAL_WITH_NEXT_STEP` (antes quedaba como `COMPLETED`).
- **Impacto:** `turn_state_sequence` refleja estado terminal real, evitando falsa señal de completado.

### 3) Endurecimiento de tests anti fake success y estados terminales

- **Archivos:**
  - `tests/test_agent_integration.py`
  - `tests/test_filesystem_dispatch.py`
  - `tests/test_app_open_verifier.py`
- **Cobertura nueva/relevante:**
  - mapping de estado terminal por `MissionStatus` (`COMPLETED`, `NEEDS_USER`, `PARTIAL_WITH_NEXT_STEP`);
  - degradacion a `UNVERIFIED` cuando verifier confirma pero no hay evidencia util;
  - `verifier skipped` sin degradacion falsa;
  - bugfix de matching de procesos para `app_open`;
  - edge-case de verificacion de `filesystem_write_text` con payload vacio.

---

## Auditoria de estados terminales (resultado)

- **COMPLETED:** se emite cuando hay evidencia confirmada/skipped coherente.
- **UNVERIFIED / UNVERIFIABLE:** se mantiene cuando la verificacion es inconclusa o se normaliza evidencia vacia.
- **FAILED:** se preserva para errores reales (tool/verifier/dispatch).
- **NEEDS_USER:** se preserva para ambiguedad/policy que requiere intervencion.
- **NEEDS_PERMISSION:** actualmente se representa publicamente como `MissionStatus.NEEDS_USER` con `termination_reason` de policy.
- **PARTIAL_WITH_NEXT_STEP:** ahora visible como estado terminal de trace para `MissionStatus.PARTIAL`.

---

## Verificacion de `_normalize_tool_result_evidence`

Chequeado contra los casos solicitados:

- ejecucion fallida: **no confunde** (si `result.ok=False`, no normaliza a exito);
- ejecucion exitosa no verificable: **no confunde** (queda `UNVERIFIED/UNVERIFIABLE`);
- bloqueada por policy: **no aplica** porque no llega a `_execute_tool_call`;
- necesita usuario: **no confunde** (se resuelve por `compute_mission_status`/policy);
- parcial: **no confunde** (ahora traza terminal como `PARTIAL_WITH_NEXT_STEP`).

---

## Que NO se toco (a proposito)

- voz/camara/UI/drag-drop;
- browser avanzado/Playwright;
- file processor grande;
- Gemini/cloud;
- `generated_code`;
- hardcodes por app en el core;
- refactor grande de arquitectura.

---

## Tests corridos y resultados

### Nuevos/segunda pasada (integration)

`python -m pytest tests/test_agent_integration.py -k "skipped_verifier_can_still_finish_completed_without_fake_success or confirmed_without_evidence_is_downgraded_to_unverified or partial_mission_uses_partial_with_next_step_terminal_state or needs_user_maps_to_needs_user_terminal_state or trace_exposes_canonical_turn_states or dispatcher_exception_does_not_report_success"`

- **6 passed**, 83 deselected.

### Subsets previos (regresion primera pasada)

`python -m pytest tests/test_agent_integration.py -k "trace_exposes_canonical_turn_states or empty_ok_tool_result_is_not_treated_as_completed or dispatcher_exception_does_not_report_success or trivial_input_does_not_call_tools or unverified_action_reply_is_evidence_based"`

- **5 passed**, 84 deselected.

`python -m pytest tests/test_agent_integration.py -k "trivial_input_does_not_call_tools or question_returns_trivial_no_tools or identity_text_ignores_spurious_tool_call or empty_ok_tool_result_is_not_treated_as_completed or dispatcher_exception_does_not_report_success or unverified_action_reply_is_evidence_based or no_tool_calls_action_with_no_target_asks_user or llm_user_approved_flag_does_not_execute_high_risk_tool"`

- **8 passed**, 81 deselected.

### Suites relevantes solicitadas

`python -m pytest tests/test_terminal_dispatch.py tests/test_filesystem_dispatch.py tests/test_verifier.py tests/test_resolver.py tests/test_security.py tests/test_app_resolver.py tests/test_app_open_verifier.py`

- **127 passed**, 1 warning (pywinauto threading mode).

---

## Riesgos restantes

- `MissionStatus` publico sigue en seis estados (`partial`, etc.). La semantica `NEEDS_PERMISSION` vive en `termination_reason`; si se quiere exponer como estado publico separado, eso ya seria cambio de contrato (no recomendado en esta pasada).
- La normalizacion anti evidencia vacia puede volver mas estrictos algunos handlers legacy que antes “pasaban”; es deseable, pero puede requerir ajustes menores en wording/tests si aparece algun edge adicional.

---

## Proximos pasos recomendados

1. Agregar test parametrico para **todos** los `MissionStatus` publicos y su estado terminal esperado en trace.
2. Añadir checks equivalentes para tools de web simple (`web_open_url`, `web_extract`) en modo edge-case de evidencia.
3. Mantener el foco en regresiones reales de texto antes de cualquier feature nueva.

