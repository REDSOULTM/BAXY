# V2 Import Round 11b — user_approved provenance hardening

Fecha: 2026-05-04.
Scope: solo `Carter_v3/`.

## 1. Objetivo

Cerrar `R-V3-T2`: el LLM podia emitir `user_approved=true` en una tool
`HIGH-risk` y destrabar policy sin aprobacion humana real.

## 2. Diseno elegido

Se eligio la **Opcion A**.

- El agent loop guarda una `PendingToolApproval` cuando una tool
  `HIGH-risk` queda bloqueada por aprobacion faltante.
- Si el usuario confirma en el turno siguiente, el loop crea una
  provenance estructural `ToolApproval(..., approved_by="user_text")`.
- `PolicyEngine.classify_tool()` solo acepta esa provenance externa para
  destrabar `HIGH-risk`.
- El campo `user_approved` del LLM queda ignorado para gating.

Se rechazo la opcion B porque habria roto el flujo real de
confirmacion conversacional y habria dejado la aprobacion solo en manos
del launcher.

## 3. Cambio aterrizado

### `src/carter_v3/security/policy.py`

- Nuevo `ToolApproval` con fingerprint estructural de argumentos.
- `classify_tool(..., approval=...)`:
  - ignora `arguments["user_approved"]`,
  - acepta solo `approved_by="user_text"`,
  - mantiene `CRITICAL` bloqueado siempre.

### `src/carter_v3/session_state.py`

- Nueva `PendingToolApproval`.
- Nuevos helpers:
  - `remember_tool_approval_request()`
  - `tool_approval_candidate()`
  - `clear_pending_tool_approval()`

### `src/carter_v3/turn_support.py`

- Nuevo `classify_tool_approval()` con salida JSON corta
  `{"approve": true|false}`.
- Sin listas de keywords; la aprobacion se resuelve por el turno de
  confirmacion pendiente.

### `src/carter_v3/agent.py`

- Sanea `user_approved` al materializar tool calls del LLM.
- Registra acciones `HIGH-risk` bloqueadas para el turno siguiente.
- Si el usuario confirma, reejecuta la accion pendiente con
  `ToolApproval` confiable.
- Solo en el boundary interno del dispatcher reinyecta
  `user_approved=True` para compatibilidad con helpers como
  `filesystem_delete`; esa bandera ya no viene del LLM.
- Cuando una tool queda bloqueada y no corre nada, la reply publica usa
  `compose_blocked_reply(...)` en vez de texto potencialmente engañoso
  del modelo.

## 4. Tests nuevos

### `tests/test_security.py`

- `test_policy_high_tool_ignores_llm_user_approved_flag_without_provenance`
- `test_policy_high_tool_allowed_with_human_approval_provenance`
- `test_policy_critical_tool_always_blocks_with_llm_flag`
- `test_policy_critical_tool_always_blocks_with_human_approval_provenance`

Cobertura:
- prueba que `user_approved=True` del LLM NO destraba `HIGH`,
- prueba que provenance humana SI destraba `HIGH`,
- prueba que `CRITICAL` sigue bloqueado en ambos caminos.

### `tests/test_agent_integration.py`

- `test_llm_user_approved_flag_does_not_execute_high_risk_tool`
- `test_human_confirmation_executes_pending_high_risk_tool`

Cobertura:
- prueba el loop real `blocked -> pending approval -> user confirmation`,
- prueba que la tool no se ejecuta en el primer turno,
- prueba que si se ejecuta en el segundo turno confirmado,
- prueba que el flag `user_approved` no queda expuesto en
  `result.tool_calls`, pero si llega internamente al dispatcher
  confiable.

## 5. Validacion real

```text
python -m pytest -q
-> PASS (suite completa, exit 0, 313 tests)

python audit/hardcode_guard.py
-> hardcode_guard: clean (54 files scanned)
```

```text
python audit/full_matrix_runner.py --mode live-safe --label round_11_provenance_full --out audit/runs/round_11_provenance_full.json
-> global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=1308.7ms

python audit/full_matrix_runner.py --mode live-safe --category 11 --label round_11_provenance_cat11 --out audit/runs/round_11_provenance_cat11.json
-> global=100.0% cat11=100.0% p95=1348.5ms
```

## 6. Resultado

- `R-V3-T2` queda cerrado.
- `C11` se mantiene en `100.0%`.
- El global no baja: sigue `100.0%`.
- `CRITICAL` continua bloqueado aunque el usuario confirme.

## 7. Residual que sigue abierto

- `R-V3-T1`: allow-list de terminal deliberadamente pequena.
- `R-V3-T3`: cobertura live de `terminal_run_command` sigue en unit
  tests, no en matriz live-safe.
- `R-V3-T4`: la latencia de cat10 sigue reflejando trabajo real de
  `web_extract`.

## 8. Veredicto

El bypass de provenance queda eliminado sin romper el flujo conversacional
real: el LLM no puede self-approve, pero el usuario si puede confirmar y
destrabar de forma estructural una accion `HIGH-risk` pendiente.
