# Round 11 - user_approved provenance hardening

Modelo recomendado:

- Mejor: `GPT-5.4`
- Razonamiento: `High`
- Fallback: `Claude Opus 4.7`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Cerrar R-V3-T2: el campo `user_approved=True` en los argumentos de una
tool call puede ser auto-generado por el LLM para destrabar gates de
policy HIGH-risk sin que ningun humano real lo haya aprobado.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md` (especialmente R-V3-T2)
- `Carter_v3/src/carter_v3/security/policy.py`
- `Carter_v3/src/carter_v3/contracts.py`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/turn_support.py`
- `Carter_v3/tests/test_security.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_11_LOG.md`

EL PROBLEMA EXACTO
Hoy en `PolicyEngine.classify_tool()`:
- si una tool es HIGH-risk y `arguments.get("user_approved") == True`,
  el gate se destrava.
- El LLM puede incluir `"user_approved": true` en su tool call sin que
  ningun humano real haya dicho nada.
- Solo los patterns CRITICAL (rm -rf, format, etc.) ignoran `user_approved`.
- Esto significa que `winget install <cualquier-cosa>` con `user_approved=True`
  generado por el LLM se ejecutaria.

MISION
Distinguir aprobacion de provenance humana real de `user_approved` generado
por el LLM. Solo la primera debe destrabar gates HIGH-risk.

DISENO REQUERIDO
La solucion debe ser estructural, no cosmetica:

Opcion A (recomendada): el agent loop gestiona una lista de tools
aprobadas por el humano en el turno actual. Cuando el usuario escribe
"si, hazlo" o "aprobado" o acepta un prompt de confirmacion, el agent
anota `{tool_name, turn_id, approved_by="user_text"}` en el `TurnContext`
(o `SessionState`). El `PolicyEngine.classify_tool()` recibe ese contexto
y solo destrava HIGH-risk si la tool aparece en esa lista con
`approved_by="user_text"`. Un `user_approved=True` del LLM sin ese
contexto sigue siendo HIGH-risk bloqueado.

Opcion B (alternativa mas simple): eliminar `user_approved` del schema
de tools publicas completamente. Las tools HIGH-risk solo se ejecutan
si el turno viene con `policy_override` en el `AgentContext` puesto
por el launcher real, nunca por el LLM.

Elige la opcion mas defensible que no rompa el flujo real de uso.

REGLAS
- Cero nuevas keyword lists para detectar "aprobacion" en texto libre.
- La aprobacion humana se detecta estructuralmente (turno previo de tipo
  `user_confirmation` con `pending_action` matcheado, o flag en contexto
  puesto por el caller).
- Si el LLM emite `user_approved=True` sin provenance, la policy lo ignora
  silenciosamente (no necesita alertar al usuario; simplemente mantiene el bloqueo).
- No cambiar los contratos publicos de `mission_status` ni `VerifiedOutcome`.
- No agregar tools al catalogo.

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_11_provenance_full --out audit/runs/round_11_provenance_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 11 --label round_11_provenance_cat11 --out audit/runs/round_11_provenance_cat11.json`

C11 debe mantenerse en 100%.
El global no debe bajar.
Agrega tests especificos en `tests/test_security.py` que:
- confirmen que `user_approved=True` del LLM NO destrava HIGH-risk
- confirmen que aprobacion via provenance humano SI destrava HIGH-risk
- confirmen que CRITICAL sigue bloqueado en ambos casos

ENTREGA
1. Que diseno elegiste y por que
2. Que cambiaste exactamente
3. Tests nuevos y por que cubren el contrato
4. Resultados reales de runners
5. Residual que sigue abierto
6. Updates en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_11_LOG.md`
```
