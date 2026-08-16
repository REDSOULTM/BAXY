# THIRD PASS GUI PERCEPTION REPORT

## Alcance de esta pasada

Pasada controlada para base mínima GUI/percepción on-demand, sin convertir Carter en sistema de visión completo.

- Sin voz
- Sin cámara física
- Sin UI/HUD
- Sin cloud/Gemini obligatorio
- Sin generated_code
- Sin hardcodes por app en core

---

## Qué se tomó de Mark (solo inspiración limitada)

- separar mejor etapas internas de flujo GUI/percepción (plan -> acción -> verificación);
- tratar screen/gui como capa on-demand, no siempre activa;
- reforzar que GUI sin readback externo no puede asumirse como completada.

## Qué se rechazó de Mark

- dependencia Gemini/cloud en flujo de percepción;
- ejecución de código generado;
- respuestas tipo "Done" por defecto;
- automatización agresiva sin verificación causal.

## Qué quedó en backlog

- OCR/VLM local real;
- screen understanding avanzado;
- pipeline percepción más rico (sin romper núcleo texto);
- mejoras de verificación GUI por señales externas adicionales.

---

## Cambios implementados (mínimos)

1. **Trazabilidad interna `NEEDS_PERMISSION`**
   - `MissionStatus` público se mantiene.
   - cuando la terminación es por permiso/policy, el terminal interno en `turn_state_sequence` ahora es `NEEDS_PERMISSION` (antes `NEEDS_USER`).

2. **Estados canónicos internos para GUI/percepción**
   - agregados: `OBSERVING_SCREEN`, `GUI_PLANNING`, `GUI_ACTING`, `VERIFYING_SCREEN`.
   - emitidos solo en flujos screen/gui reales.

3. **Contrato mínimo GUI endurecido**
   - `gui_click` y `gui_type` suben a `RiskLevel.HIGH` (requieren aprobación policy).
   - verificador `gui_action` ya no confirma por defecto: `ok=True` sin readback externo => `UNVERIFIABLE`.

---

## Archivos modificados

- `THIRD_PASS_GUI_PERCEPTION_AUDIT.md` (nuevo)
- `THIRD_PASS_GUI_PERCEPTION_PLAN.md` (nuevo)
- `src/carter_v3/trace.py`
- `src/carter_v3/agent.py`
- `src/carter_v3/tools/catalog.py`
- `src/carter_v3/tools/verifier.py`
- `tests/test_agent_integration.py`

---

## Tests agregados/ajustados

En `tests/test_agent_integration.py`:

- `test_simple_chat_inputs_never_activate_screen_or_gui`
- `test_ambiguous_gui_action_needs_user_without_execution`
- `test_gui_high_risk_requires_permission_and_traces_needs_permission`
- `test_gui_action_without_external_readback_ends_unverified_with_approval`
- `test_gui_partial_mission_traces_partial_with_next_step`
- `test_explicit_screenshot_route_emits_observing_and_screen_states`
- ajustes de expectativas de trazabilidad en tests de matriz/policy para `NEEDS_PERMISSION`.

---

## Tests corridos y resultados

1. GUI/percepción + regresiones clave integración:
   - `python -m pytest tests/test_agent_integration.py -k "simple_chat_inputs_never_activate_screen_or_gui or ambiguous_gui_action_needs_user_without_execution or gui_high_risk_requires_permission_and_traces_needs_permission or gui_action_without_external_readback_ends_unverified_with_approval or gui_partial_mission_traces_partial_with_next_step or explicit_screenshot_route_emits_observing_and_screen_states or mission_status_terminal_trace_matrix or policy_high_risk_no_approval_keeps_needs_user_terminal_state or empty_ok_tool_result_is_not_treated_as_completed or terminal_confirmed_without_evidence_is_downgraded_to_unverified"`
   - **Resultado:** `19 passed, 88 deselected`

2. Filesystem anti-fake-success:
   - `python -m pytest tests/test_filesystem_dispatch.py -k "fs_write_verifier_needs_evidence_not_empty_stub"`
   - **Resultado:** `1 passed`

3. app_open normalization regression:
   - `python -m pytest tests/test_app_open_verifier.py -k "matching_process_names_is_case_insensitive_and_strips_exe"`
   - **Resultado:** `1 passed`

Lint:
- `ReadLints` sobre archivos editados -> sin errores.

---

## Riesgos restantes

- GUI real sigue siendo básica (click/type stub en dispatch por defecto); la seguridad mejoró, pero la utilidad completa depende de implementación futura.
- `NEEDS_ENVIRONMENT` sigue conceptual/semántico (actualmente expresado por `needs_user` + `termination_reason`), no como `MissionStatus` público nuevo.
- verificación GUI todavía depende de ampliar probes de readback para poder cerrar más casos como `COMPLETED`.

---

## Próximos pasos recomendados (mínimos)

1. Mantener screen/gui on-demand y ampliar tests de no-regresión en cada nueva tool GUI.
2. Si se implementa GUI real (no stub), exigir siempre evidencia externa mínima para `CONFIRMED`.
3. Definir guideline estable para `termination_reason` (`needs_permission`, `needs_environment`, etc.) sin romper contrato público.

