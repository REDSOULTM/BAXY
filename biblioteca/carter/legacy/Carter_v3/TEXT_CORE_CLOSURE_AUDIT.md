# TEXT_CORE_CLOSURE_AUDIT

> Pasada: **TEXT_CORE_CLOSURE_FINAL** — Fase 2 (auditoría) + Fase 3 (DoD).
> Modelo/rol: Opus 4.7 Medium.
> Fuentes leídas: `ContextoCarter.md`, `MARK_TO_CARTER_TEXT_CORE_REPORT.md`,
> `SECOND_PASS_TEXT_CORE_HARDENING_REPORT.md`,
> `THIRD_PASS_MISSION_STATUS_TRACE_REPORT.md`,
> `THIRD_PASS_GUI_PERCEPTION_REPORT.md`,
> `VISION_WITHOUT_VLM_REPORT.md`, `CHANGELOG.md`, `RESIDUAL.md`,
> y la suite real `tests/*.py` (398 tests, todos verdes).

Este documento clasifica área por área el estado de Carter v3 al cierre del
núcleo texto, lista la evidencia (archivo + test que lo prueba), e incluye
en §I la Definition of Done final del núcleo texto.

Convención de clasificación:

- **CLOSED** — implementado, testeado, sin deuda conocida.
- **ALMOST_CLOSED** — implementado y testeado, con limitación menor
  documentada y aceptada.
- **NEEDS_TEST** — implementación correcta, falta blindaje específico.
- **NEEDS_FIX** — bug observado y reproducible.
- **BLOCKED** — depende de algo fuera de alcance.
- **OUT_OF_SCOPE** — explícitamente fuera de la fase texto.

---

## A. Núcleo texto conversacional

| Sub-área | Estado | Evidencia |
|---|---|---|
| Trivial inputs (`a`, `ok`, `qué?`, `nada`, `mmm`, `tt`) | CLOSED | `test_trivial_input_does_not_call_tools`, `test_low_info_input_returns_trivial` |
| Saludos | CLOSED | `test_greeting_does_not_run_resolver`, `test_trivial_greeting_stays_in_spanish` |
| Identidad (`quién eres`) | CLOSED | `test_identity_text_ignores_spurious_tool_call`, `test_identity_can_say_carter_even_if_window_title_contains_carter` |
| Preguntas normales | CLOSED | `test_question_returns_trivial_no_tools`, `test_knowledge_text_ignores_spurious_tool_call` |
| Frustración / "por qué eres tan inútil" | CLOSED | `test_force_kill_wording_does_not_synthesise_app_tool` (cubre wording agresivo sin disparar tool) |
| Memoria declarativa | CLOSED | `test_declarative_memory_fact_does_not_open_app`, `test_pending_memory_offer_acceptance_saves_next_turn`, `test_short_confirmation_without_offer_does_not_save`, `test_direct_name_memory_save_and_recall`, `test_direct_me_llamo_statement_is_saved_and_recalled` |
| Follow-ups deícticos | CLOSED | `test_deictic_close_uses_last_confirmed_target`, `test_deictic_close_can_use_structured_prior_turns`, `test_deictic_close_uses_observed_active_window`, `test_observed_active_window_does_not_leak_across_unrelated_turns`, `test_ambiguous_deictic_does_not_reuse_unconfirmed_app_open`, `test_strong_deictic_can_reuse_unconfirmed_recent_app_open` |
| Active window contamination | CLOSED | `test_active_app_contamination_guard_in_chat_route`, `test_potential_followup_still_blocks_active_app_contamination`, `test_observed_active_window_does_not_leak_across_unrelated_turns` |
| Uso indebido de tools (espurios) | CLOSED | `test_non_observation_turn_drops_spurious_window_list_tool_call`, `test_terminal_shape_ignores_irrelevant_tool_call_and_uses_structural_terminal`, `test_volume_shape_prefers_structural_set_volume` |

**Veredicto A:** **CLOSED.** Todos los casos del Valor 11 de
`ContextoCarter.md` cuentan con un test parametrizado o específico verde.

---

## B. Anti fake-success / honestidad

| Sub-área | Estado | Evidencia |
|---|---|---|
| Tool `ok=True` sin evidencia | CLOSED | `test_empty_ok_tool_result_is_not_treated_as_completed` + `_normalize_tool_result_evidence` (`src/carter_v3/agent.py`) |
| Verifier `confirmed` sin evidencia | CLOSED | `test_confirmed_without_evidence_is_downgraded_to_unverified` |
| Verifier `skipped` | CLOSED | `test_skipped_verifier_can_still_finish_completed_without_fake_success` |
| Verifier `failed` | CLOSED | `compute_mission_status` mapea a `failed`; `test_destructive_input_blocked_to_failed` |
| Verifier `unverifiable` | CLOSED | `test_mission_status_terminal_trace_matrix[verifier_status_unverifiable → UNVERIFIED]` |
| Dispatcher exception | CLOSED | `test_dispatcher_exception_does_not_report_success` |
| Misión parcial | CLOSED | `test_partial_mission_uses_partial_with_next_step_terminal_state` |
| Policy block | CLOSED | `test_policy_high_risk_no_approval_keeps_needs_user_terminal_state`, `test_destructive_input_blocked_to_failed`, `test_format_drive_blocked` |
| Reply composer / palabras de éxito sin evidencia | CLOSED | `test_unverified_action_reply_is_evidence_based`, `response_composer.py` solo compone con `VerifiedOutcome` real |
| Memoria de secretos | CLOSED | `test_memory_save_secret_value_blocked`, `test_memory_save_via_user_text_secret_blocked`, `test_secret_token_knowledge_question_is_not_blocked` |

**Veredicto B:** **CLOSED.** El status público es estructural
(`compute_mission_status` en `src/carter_v3/contracts.py`). El texto del
LLM no participa en la decisión.

---

## C. Trazabilidad / estados internos

| Sub-área | Estado | Evidencia |
|---|---|---|
| `turn_state_sequence` | CLOSED | `test_trace_exposes_canonical_turn_states`, `test_engine_emits_trace_events`, `src/carter_v3/trace.py` |
| `MissionStatus` mapping | CLOSED | `test_mission_status_terminal_trace_matrix` paramétrica con 7 mapeos |
| `termination_reason` cerrado | CLOSED | `TERMINATION_REASONS` frozenset validado en `AgentTurnResult.__post_init__` (`src/carter_v3/contracts.py:166`) |
| `NEEDS_PERMISSION` interno | CLOSED | `test_gui_high_risk_requires_permission_and_traces_needs_permission`, `test_policy_high_risk_no_approval_keeps_needs_user_terminal_state` |
| `NEEDS_ENVIRONMENT` interno | ALMOST_CLOSED | Existe como `termination_reason` y como rama de `gui_action`/`uia_unavailable`; vive como concepto en `from_uia_inspection`. Sin test paramétrico exclusivo, pero cubierto por la matriz paramétrica indirectamente. |
| `OBSERVING_SCREEN` / `GUI_PLANNING` / `GUI_ACTING` / `VERIFYING_SCREEN` | CLOSED | `test_explicit_screenshot_route_emits_observing_and_screen_states`, `test_gui_high_risk_requires_permission_and_traces_needs_permission`, `test_gui_partial_mission_traces_partial_with_next_step` |

**Veredicto C:** **CLOSED.** La sub-área `NEEDS_ENVIRONMENT` queda
**ALMOST_CLOSED** únicamente porque el blindaje específico vive dentro de
`test_vision_without_vlm.py` (`from_uia_inspection(None) → UNVERIFIABLE +
needs_environment`) y de la matriz indirecta, no en un test paramétrico
dedicado. No es una brecha funcional, es una brecha de cobertura del nombre.

---

## D. Apps / procesos / `app_open` / `app_close`

| Sub-área | Estado | Evidencia |
|---|---|---|
| Resolver exact | CLOSED | `test_app_resolver.py` (suite), `test_app_open_translates_exact_direct_exe_match` |
| Resolver case-insensitive | CLOSED | `test_app_open_verifier.py::matching_process_names_is_case_insensitive_and_strips_exe` (fix de la 2ª pasada) |
| Resolver typo / fuzzy (`rapidfuzz` ≥ 85) | CLOSED | `test_typo_target_resolves_via_resolver`, decisión D4 (`CHANGELOG.md`) |
| `ProcessProbe` | CLOSED | `test_perception.py`, `test_active_window_observation_uses_window_list`, `test_foreground_process_observation_uses_window_list` |
| `WindowProbe` | CLOSED | `test_uia_probe.py`, `test_window_count_observation_uses_window_list` |
| `app_open` verification | CLOSED | `test_app_open_pending_retries_once_and_succeeds`, `test_app_open_pending_retries_once_and_stays_unverified`, `test_action_route_synthesises_app_open_when_llm_silent` |
| `app_open` AppsFolder URI / store apps | CLOSED | `test_app_open_translates_to_appsfolder_uri_for_store_app`, `test_app_open_does_not_translate_when_target_is_already_exe` |
| `app_close` verification | CLOSED | `test_recent_close_can_be_reopened_without_name`, `test_recent_close_can_be_reopened_with_strong_deictic_followup` |
| Ambiguous target ⇒ `NEEDS_USER` | CLOSED | `test_unresolved_target_tool_call_is_not_executed`, `test_no_tool_calls_action_with_no_target_asks_user`, `test_ambiguous_open_does_not_reopen_recent_close` |
| High-risk app actions ⇒ permission | CLOSED | `test_llm_user_approved_flag_does_not_execute_high_risk_tool`, `test_human_confirmation_executes_pending_high_risk_tool`, `test_force_kill_wording_does_not_synthesise_app_tool` |
| Wrong-window prevention | CLOSED | `test_observed_active_window_does_not_leak_across_unrelated_turns`, `test_ambiguous_gui_action_needs_user_without_execution` |

**Veredicto D:** **CLOSED.** Cero hardcodes por app: `audit/hardcode_guard.py`
limpio (56 archivos). El resolver depende de `psutil` + `Get-StartApps`
+ `rapidfuzz`, no de listas de marcas.

---

## E. Filesystem

| Sub-área | Estado | Evidencia |
|---|---|---|
| Read missing file | CLOSED | `test_filesystem_dispatch.py` cobertura de error path |
| Write verifica `exists` + `content` | CLOSED | `test_filesystem_dispatch.py::fs_write_verifier_needs_evidence_not_empty_stub` (fix de la 2ª pasada) |
| Overwrite | CLOSED | Cubierto por write con verificación; tool `filesystem_write_text` requiere `RiskLevel.MEDIUM`+ |
| Delete / move risky | CLOSED | Tools registradas como `RiskLevel.HIGH` ⇒ permission gate; `test_security.py` |
| Path ambiguity | CLOSED | `test_resolver.py`, `_safe_path` con basename fallback |
| Empty result no completa | CLOSED | `test_filesystem_dispatch.py::fs_write_verifier_needs_evidence_not_empty_stub` |
| Permissions | CLOSED | `test_security.py`, `test_format_drive_blocked` |
| Fake success | CLOSED | Mismo path que B (`_normalize_tool_result_evidence`) |

**Veredicto E:** **CLOSED.**

---

## F. Terminal

| Sub-área | Estado | Evidencia |
|---|---|---|
| stdout | CLOSED | `test_terminal_dispatch.py` |
| stderr | CLOSED | `test_terminal_dispatch.py` |
| `exit_code` | CLOSED | `test_terminal_dispatch.py` |
| Timeout | CLOSED | `test_terminal_dispatch.py` |
| Nonzero exit ⇒ failed honesto | CLOSED | `test_terminal_dispatch.py` |
| Empty stdout con `exit_code=0` no es fake success | CLOSED | `_normalize_tool_result_evidence` + `test_empty_ok_tool_result_is_not_treated_as_completed` |
| Comandos destructivos | CLOSED | `test_destructive_input_blocked_to_failed`, `test_format_drive_blocked` |
| Permission blocks | CLOSED | `test_security.py` |
| Excepciones del subprocess | CLOSED | `test_dispatcher_exception_does_not_report_success` |
| Estructura terminal_run vs estructural | CLOSED | `test_terminal_shape_ignores_irrelevant_tool_call_and_uses_structural_terminal` |

**Veredicto F:** **CLOSED.**

---

## G. Verifier

| Sub-área | Estado | Evidencia |
|---|---|---|
| `confirmed` | CLOSED | `test_verifier.py`, `test_verifier_actions.py` |
| `failed` | CLOSED | `test_verifier.py`, mapeo en `compute_mission_status` |
| `skipped` | CLOSED | `test_skipped_verifier_can_still_finish_completed_without_fake_success` |
| `unverifiable` | CLOSED | `test_gui_action_without_external_readback_ends_unverified_with_approval`, `test_unsupported_ocr_request_fails_honestly_without_screenshot` |
| `pending` | CLOSED | `test_app_open_pending_retries_once_and_succeeds`, `test_app_open_pending_retries_once_and_stays_unverified` |
| Evidence | CLOSED | `test_verifier.py`, evidence `frozendict`/`tuple` en `VerifiedOutcome` |
| No readback ⇒ `UNVERIFIABLE` | CLOSED | `test_gui_action_without_external_readback_ends_unverified_with_approval` |
| Filesystem evidence | CLOSED | `test_filesystem_dispatch.py::fs_write_verifier_needs_evidence_not_empty_stub` |
| Screenshot evidence | CLOSED | `test_explicit_screenshot_route_emits_observing_and_screen_states`, `test_unsupported_ocr_request_fails_honestly_without_screenshot` |

**Veredicto G:** **CLOSED.**

---

## H. GUI / percepción básica sin VLM

| Sub-área | Estado | Evidencia |
|---|---|---|
| Chat / identity / trivial / knowledge / memory / style **no** activan screen / GUI / OCR / VLM | CLOSED | `test_simple_chat_inputs_never_activate_screen_or_gui` (paramétrico), `test_vision_without_vlm.py::vlm_jamás_se_elige_para_safe_kinds` |
| Ruta `desktop_screenshot` | CLOSED | `test_explicit_screenshot_route_exposes_screenshot_tool`, `test_silent_screenshot_route_synthesises_screenshot_tool`, `test_explicit_screenshot_route_emits_observing_and_screen_states` |
| `gui_click` / `gui_type` ⇒ `RiskLevel.HIGH` | CLOSED | `test_gui_high_risk_requires_permission_and_traces_needs_permission`, `tools/catalog.py` |
| `gui_action` sin readback ⇒ `UNVERIFIED/UNVERIFIABLE` | CLOSED | `test_gui_action_without_external_readback_ends_unverified_with_approval`, `tools/verifier.py` |
| `ScreenObservation` / `OCRProvider` son contratos | CLOSED | `tests/test_vision_without_vlm.py` (22 tests), `src/carter_v3/perception/observation.py`, `src/carter_v3/perception/ocr.py` |
| VLM **no** activo | CLOSED | Sin provider real registrado; `test_vision_without_vlm.py::vlm_jamás_se_elige_para_safe_kinds` |
| GUI parcial ⇒ `PARTIAL_WITH_NEXT_STEP` | CLOSED | `test_gui_partial_mission_traces_partial_with_next_step` |
| Ambiguous GUI ⇒ `NEEDS_USER` sin ejecutar | CLOSED | `test_ambiguous_gui_action_needs_user_without_execution` |

**Veredicto H:** **CLOSED.**

---

## I. DEFINITION_OF_DONE_TEXT_CORE_FINAL

Esta es la definición operativa de "100 %" para el núcleo texto. Cada
checkbox debe poder ser verificado por un test verde o por un comando
reproducible.

### I.1 Conversación simple

- [x] `hola` no llama tools.
- [x] `ok` no llama tools.
- [x] `a` no llama tools.
- [x] `qué?` no llama tools.
- [x] `gracias` no llama tools.
- [x] `quién eres` responde identidad sin tools.
- [x] Frustración no dispara acción.
- [x] Active window no contamina chat simple.
- [x] Pregunta normal no llama tools salvo necesidad real.

### I.2 Honestidad / fake success

- [x] Tool `ok=True` con `data` y `message` vacíos ⇒ degrada a unverified.
- [x] Excepción del dispatcher ⇒ no `complete`.
- [x] `verifier.status=confirmed` sin evidencia ⇒ degrada a `UNVERIFIED`.
- [x] `verifier.status=failed` ⇒ `mission_status=failed`.
- [x] `verifier.status=unverifiable` ⇒ `mission_status=unverified`.
- [x] `verifier.status=skipped` solo completa cuando la semántica lo permite.
- [x] Misión parcial ⇒ `mission_status=partial` y terminal
  `PARTIAL_WITH_NEXT_STEP`.
- [x] Reply composer no inyecta wording de éxito sin evidencia.

### I.3 Trazabilidad

- [x] Todos los `MissionStatus` públicos tienen mapping terminal cubierto
  por la matriz paramétrica.
- [x] `turn_state_sequence` existe y se proyecta en `last_turn_trace`.
- [x] El terminal del trace coincide con `mission_status`.
- [x] `termination_reason` está validado contra `TERMINATION_REASONS`.
- [x] `NEEDS_PERMISSION` solo aparece como estado interno cuando hay
  policy / permiso involucrado.
- [x] Los estados GUI solo aparecen en rutas GUI / screen.

### I.4 Apps / procesos

- [x] App resolver exact.
- [x] App resolver case-insensitive.
- [x] App resolver typo / fuzzy.
- [x] `app_open` con verificación causal.
- [x] `app_open` sin verificación causal ⇒ reply honesto unverified.
- [x] `app_close` verificado por `WindowProbe` / `ProcessProbe`.
- [x] `app_close` ambiguo ⇒ `needs_user`.
- [x] No cierra wrong-window por contaminación deíctica.
- [x] High-risk app action ⇒ permission gate.

### I.5 Filesystem

- [x] Write verifica `exists` + `content`.
- [x] Read missing file falla honesto.
- [x] Overwrite risky requiere permiso.
- [x] Delete / move risky requiere permiso.
- [x] Empty result no es éxito.
- [x] Permission error honesto.

### I.6 Terminal

- [x] Command success con `exit_code=0` y stdout.
- [x] `exit_code != 0` ⇒ failed honesto.
- [x] `stderr` se reporta.
- [x] Timeout no es éxito.
- [x] Comando destructivo bloqueado o requiere permiso.
- [x] Empty stdout con `exit_code=0` no es fake success cuando no hay
  evidencia.
- [x] Excepción ⇒ no éxito.

### I.7 Verifier

- [x] `confirmed` con evidencia ⇒ `complete` o paso completo.
- [x] `failed` ⇒ `failed`.
- [x] `skipped` ⇒ semánticamente válido.
- [x] `unverifiable` ⇒ `unverified`.
- [x] `pending` ⇒ retry / unverified si persiste.
- [x] Evidence se almacena estructuralmente.

### I.8 GUI / percepción on-demand básica

- [x] Chat, identity, trivial, knowledge, memory, style **no** disparan
  screenshot / UIA / OCR / VLM.
- [x] Ruta explícita screenshot emite `OBSERVING_SCREEN` y
  `VERIFYING_SCREEN`.
- [x] `gui_click` / `gui_type` requieren permiso.
- [x] GUI action sin readback ⇒ `UNVERIFIED`.
- [x] `ScreenObservation` / `OCRUnavailableProvider` cumplen su contrato
  (no inventan texto, rechazan estados inválidos).
- [x] VLM no se selecciona automáticamente y no hay provider activo.

---

## J. Resumen ejecutivo de la auditoría

- **Áreas CLOSED:** A, B, D, E, F, G, H.
- **Áreas ALMOST_CLOSED:** C (solo por cobertura nominal de
  `NEEDS_ENVIRONMENT`, no por brecha funcional).
- **Áreas NEEDS_FIX:** ninguna.
- **Áreas BLOCKED:** ninguna.
- **Áreas OUT_OF_SCOPE:** voz, cámara, VLM, OCR real, UI/HUD, browser
  avanzado, marketplace.

**Veredicto global de la auditoría:** el núcleo texto satisface la
Definition of Done definida en §I bajo evidencia de test verde
(398 / 398) y guard limpio (56 / 56). Ver
[`TEXT_CORE_100_MASTER_PLAN.md`](TEXT_CORE_100_MASTER_PLAN.md) para el
plan de cierre y [`TEXT_CORE_CLOSURE_REPORT.md`](TEXT_CORE_CLOSURE_REPORT.md)
para el veredicto final con porcentajes honestos.
