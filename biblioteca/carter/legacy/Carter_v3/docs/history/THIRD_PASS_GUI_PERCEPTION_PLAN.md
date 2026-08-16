# THIRD PASS GUI PERCEPTION PLAN

Plan mínimo (máximo 3 cambios), sin features grandes.

## Cambio 1 — NEEDS_PERMISSION interno en trazabilidad

- **Objetivo:** distinguir internamente `NEEDS_USER` vs `NEEDS_PERMISSION` sin romper contrato público.
- **Archivos:**
  - `src/carter_v3/trace.py`
  - `src/carter_v3/agent.py`
- **Implementación mínima:**
  - agregar estado interno `NEEDS_PERMISSION` en `TURN_STATES`;
  - en `_finish`, mapear:
    - `mission_status=needs_user` + `termination_reason` de permiso/policy -> estado terminal `NEEDS_PERMISSION`;
    - resto de `needs_user` -> `NEEDS_USER`.
- **Riesgo:** bajo (solo metadata).

## Cambio 2 — Estados canónicos de GUI/percepción (solo trazabilidad)

- **Objetivo:** preparar trazabilidad on-demand (`OBSERVING_SCREEN`, `GUI_PLANNING`, `GUI_ACTING`, `VERIFYING_SCREEN`) sin visión pesada.
- **Archivos:**
  - `src/carter_v3/trace.py`
  - `src/carter_v3/agent.py`
- **Implementación mínima:**
  - agregar estados al set canónico;
  - emitirlos solo cuando haya flujo real screen/gui (`desktop_screenshot`, `gui_*`, `window_list`).
- **Riesgo:** bajo.

## Cambio 3 — Endurecer contrato mínimo GUI

- **Objetivo:** evitar `COMPLETED` en GUI no verificable y exigir permiso en GUI riesgoso.
- **Archivos:**
  - `src/carter_v3/tools/catalog.py`
  - `src/carter_v3/tools/verifier.py`
  - `tests/test_agent_integration.py`
- **Implementación mínima:**
  - elevar riesgo de `gui_click`/`gui_type` a `HIGH` (requiere aprobación policy);
  - cambiar `_gui_action` para que `ok=True` sin readback sea `UNVERIFIABLE` (no `CONFIRMED`);
  - agregar tests solicitados.
- **Riesgo:** medio-bajo (cambia gating de GUI hacia mayor seguridad).

---

## Tests mínimos a cubrir

- conversación simple no usa screen/gui;
- identidad no usa screen/gui;
- input trivial no usa screen/gui;
- acción GUI ambigua -> `NEEDS_USER`;
- acción GUI riesgosa -> `NEEDS_PERMISSION` interno / `needs_user` público;
- acción GUI ejecutada no verificable -> `UNVERIFIED`;
- misión parcial GUI -> `PARTIAL_WITH_NEXT_STEP`;
- policy block mantiene estado honesto.

---

## Rollback

- revertir cambios en:
  - `trace.py`
  - `agent.py`
  - `catalog.py`
  - `verifier.py`
  - tests nuevos

