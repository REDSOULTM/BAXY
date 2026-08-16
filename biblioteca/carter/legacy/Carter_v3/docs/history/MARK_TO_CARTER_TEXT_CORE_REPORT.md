# MARK TO CARTER TEXT CORE REPORT

## Que se tomo de Mark

- **Idea tomada:** estado/progreso operacional explicito por turno.
  - Adaptacion: secuencia canonica de estados en trace textual, sin UI/voz.
- **Idea tomada (parcial):** endurecer manejo de ejecucion para evitar exito optimista.
  - Adaptacion: normalizacion defensiva cuando una tool reporta `ok=True` sin evidencia util.

## Que NO se tomo y por que

- Voz, camara, UI/HUD, drag and drop: fuera de fase actual (nucleo texto).
- Browser Playwright avanzado: backlog; no es necesario para este objetivo.
- File processor universal: backlog por complejidad y acoplamiento cloud.
- Dependencia Gemini/cloud, `generated_code`, `"Done"` default, hardcodes por app: rechazado por conflicto directo con `ContextoCarter.md`.

## Archivos modificados

- `AUDIT_MARK_TO_CARTER_TEXT_CORE.md` (nuevo)
- `PLAN_MARK_INSPIRED_TEXT_CORE.md` (nuevo)
- `src/carter_v3/trace.py`
- `src/carter_v3/agent.py`
- `tests/test_agent_integration.py`

## Implementacion realizada (controlada)

1. **Trazabilidad canonica de estado**
   - `trace.py`: nuevos estados canonicos + `emit_state`.
   - `agent.py`: emision de estados en puntos clave (`RECEIVED_INPUT`, `CLASSIFYING_INTENT`, `PLANNING_TOOL_USE`, `EXECUTING_TOOL`, `VERIFYING`, estado terminal).
   - `agent.py`: proyeccion `turn_state_sequence` en `last_turn_trace`.

2. **Normalizacion anti fake-success**
   - `agent.py`: `_normalize_tool_result_evidence`.
   - Si una tool de accion (no `skipped`) devuelve `ok=True` sin mensaje ni data, y el verifier la da por `confirmed/skipped`, se degrada a:
     - `ToolResult.ok=False`, `message=tool_returned_ok_without_evidence`
     - `VerifiedOutcome.status=unverifiable`

3. **Tests nuevos**
   - `test_trace_exposes_canonical_turn_states`
   - `test_empty_ok_tool_result_is_not_treated_as_completed`
   - `test_dispatcher_exception_does_not_report_success`

## Tests corridos

### Comando 1 (subset nuevo + seguridad base)

`python -m pytest tests/test_agent_integration.py -k "trace_exposes_canonical_turn_states or empty_ok_tool_result_is_not_treated_as_completed or dispatcher_exception_does_not_report_success or trivial_input_does_not_call_tools or unverified_action_reply_is_evidence_based"`

- Resultado final: **5 passed**, 80 deselected.

### Comando 2 (subset ampliado de core texto)

`python -m pytest tests/test_agent_integration.py -k "trivial_input_does_not_call_tools or question_returns_trivial_no_tools or identity_text_ignores_spurious_tool_call or empty_ok_tool_result_is_not_treated_as_completed or dispatcher_exception_does_not_report_success or unverified_action_reply_is_evidence_based or no_tool_calls_action_with_no_target_asks_user or llm_user_approved_flag_does_not_execute_high_risk_tool"`

- Resultado: **8 passed**, 77 deselected.

### Nota de ejecucion

- No se corrio suite completa por tiempo/costo de ciclo; se corrio subset enfocado al objetivo del cambio.

## Riesgos restantes

- Puede existir algun handler edge-case que antes “pasaba” con payload vacio y ahora se degrade a `UNVERIFIED`; esto es deseado desde honestidad, pero puede cambiar expectativas de wording en casos limite.
- La secuencia de estados es nueva metadata; consumidores externos que lean `last_turn_trace` deben tratarla como extensible.

## Rollback

- Revertir cambios en:
  - `src/carter_v3/trace.py`
  - `src/carter_v3/agent.py`
  - `tests/test_agent_integration.py`
- Mantener docs de auditoria/plan/reporte como registro, o revertirlas si se desea limpieza total.

## Proximos pasos recomendados

1. Expandir tests anti fake-success a `terminal_run_command` y `filesystem_write_text` edge-cases.
2. Agregar test de estado terminal por cada `MissionStatus` publico.
3. Mantener backlog separado para ideas de Mark fuera de fase texto (sin implementarlas aun).

