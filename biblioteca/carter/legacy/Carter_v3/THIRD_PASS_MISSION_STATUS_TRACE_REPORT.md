# THIRD PASS MISSION STATUS TRACE REPORT

## Matriz final MissionStatus -> turn_state_sequence (terminal)

| MissionStatus publico | termination_reason de prueba | Estado terminal esperado |
|---|---|---|
| `complete` | `all_tools_confirmed` | `COMPLETED` |
| `partial` | `partial_some_tools_unverified` | `PARTIAL_WITH_NEXT_STEP` |
| `failed` | `all_tools_failed` | `FAILED` |
| `needs_user` | `needs_permission` | `NEEDS_USER` |
| `unverified` | `verification_inconclusive` | `UNVERIFIED` |
| `unverified` | `verifier_status_unverifiable` | `UNVERIFIED` |
| `trivial` | `trivial_chat` | `DIRECT_CHAT` |

Adicional policy/permiso (flujo real):
- high risk sin aprobacion -> `mission_status=needs_user`, `termination_reason=policy_block_high_risk_no_approval`, estado terminal `NEEDS_USER`.

---

## Tests agregados (tercera pasada)

En `tests/test_agent_integration.py`:

1. `test_mission_status_terminal_trace_matrix` (parametrico)
   - valida mapeo terminal para cada `MissionStatus` publico relevante.
2. `test_policy_high_risk_no_approval_keeps_needs_user_terminal_state`
   - valida caso real de policy/permiso.

---

## Resultados de ejecucion

### Matriz + policy (nuevos)

`python -m pytest tests/test_agent_integration.py -k "mission_status_terminal_trace_matrix or policy_high_risk_no_approval_keeps_needs_user_terminal_state"`

- **8 passed**, 89 deselected.

### Subsets relevantes previos

`python -m pytest tests/test_agent_integration.py -k "trace_exposes_canonical_turn_states or empty_ok_tool_result_is_not_treated_as_completed or dispatcher_exception_does_not_report_success or trivial_input_does_not_call_tools or unverified_action_reply_is_evidence_based"`

- **5 passed**, 92 deselected.

`python -m pytest tests/test_agent_integration.py -k "skipped_verifier_can_still_finish_completed_without_fake_success or confirmed_without_evidence_is_downgraded_to_unverified or partial_mission_uses_partial_with_next_step_terminal_state or needs_user_maps_to_needs_user_terminal_state"`

- **4 passed**, 93 deselected.

### Suite relevante no-integration

`python -m pytest tests/test_terminal_dispatch.py tests/test_filesystem_dispatch.py tests/test_verifier.py tests/test_resolver.py tests/test_security.py tests/test_app_resolver.py tests/test_app_open_verifier.py`

- **127 passed**, 1 warning (`pywinauto` threading mode).

---

## Inconsistencias encontradas

- **No se detectaron inconsistencias nuevas** en el mapeo terminal después del segundo pase.
- Confirmado: Carter no traza `COMPLETED` para `partial`, `failed`, `needs_user` ni `unverified`.
- Confirmado: policy high-risk sin aprobacion mantiene `NEEDS_USER` y reason correcto.

---

## Proximos pasos

1. Mantener esta matriz parametrica como guardrail permanente.
2. Opcional: extender matriz a termination reasons adicionales de `needs_user` (por ejemplo `ambiguity_target_unresolved`, `needs_environment`) para cobertura exhaustiva de razones.
3. No abrir nuevas features hasta cerrar regresiones reales de usuario en fase texto.

