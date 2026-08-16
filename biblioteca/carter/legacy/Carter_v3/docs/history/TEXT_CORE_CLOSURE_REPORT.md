# TEXT_CORE_CLOSURE_REPORT

> Pasada: **TEXT_CORE_CLOSURE_FINAL** — Fase 9 (reporte final).
> Modelo/rol: Opus 4.7 Medium, auditor + implementador.
> Documentos relacionados:
> [`TEXT_CORE_MASTER_CONTEXT.md`](TEXT_CORE_MASTER_CONTEXT.md),
> [`TEXT_CORE_CLOSURE_AUDIT.md`](TEXT_CORE_CLOSURE_AUDIT.md),
> [`TEXT_CORE_100_MASTER_PLAN.md`](TEXT_CORE_100_MASTER_PLAN.md),
> [`LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md`](LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md).
> Fuente de verdad sobre identidad: [`../ContextoCarter.md`](../ContextoCarter.md).

---

## 1. Resumen ejecutivo

Carter v3 alcanza el cierre del núcleo texto bajo la Definition of Done
documentada en [`TEXT_CORE_CLOSURE_AUDIT.md`](TEXT_CORE_CLOSURE_AUDIT.md) §I.

- **Suite completa:** `pytest` → **398 passed in 145.23 s** (100 %).
- **Hardcode guard:** `python audit/hardcode_guard.py` → **clean
  (56 files scanned)**.
- **Bugs nuevos detectados:** **0**.
- **Fixes nuevos aplicados:** **0** (no había bugs reales que justificaran
  cambio de código; la regla de la pasada era no inventar fixes).
- **Tests nuevos agregados:** **0** (cobertura ya satisface la DoD).
- **Documentos nuevos creados:** **5** (los obligatorios de esta pasada,
  ver §6).
- **Veredicto:** **`TEXT_CORE_READY`** — el núcleo texto cumple con la
  Definition of Done de manera reproducible y honesta. Detalle en §12.

Esta pasada **no toca código de producción** porque la auditoría
muestra que las cuatro pasadas previas (Mark-inspired,
Second-pass-hardening, Third-pass-MissionStatus,
Third-pass-GUI-perception, Vision-Without-VLM) ya cerraron las brechas
funcionales con tests dedicados. La función de esta pasada es
**firmar el cierre** con evidencia.

---

## 2. Porcentaje honesto final por área

| Área | % | Estado | Evidencia primaria |
|---|---|---|---|
| Núcleo texto conversacional | **100 %** | CLOSED | `test_agent_integration.py::trivial/identity/knowledge/memory/follow-up`, `test_perception.py`, audit §A |
| Anti fake-success / honestidad | **100 %** | CLOSED | `_normalize_tool_result_evidence` + `compute_mission_status` + tests B, audit §B |
| Trazabilidad / estados internos | **98 %** | ALMOST_CLOSED (cobertura nominal) | `test_mission_status_terminal_trace_matrix`, `test_trace_exposes_canonical_turn_states`, audit §C |
| Apps / procesos / app_open / app_close | **100 %** | CLOSED | `test_app_resolver.py`, `test_app_open_verifier.py`, hardcode_guard 0 / 0 |
| Filesystem | **100 %** | CLOSED | `test_filesystem_dispatch.py`, audit §E |
| Terminal | **100 %** | CLOSED | `test_terminal_dispatch.py`, audit §F |
| Verifier | **100 %** | CLOSED | `test_verifier.py`, `test_verifier_actions.py`, audit §G |
| GUI / percepción on-demand sin VLM | **100 %** | CLOSED | `test_vision_without_vlm.py` (22 tests) + tests gating en `test_agent_integration.py`, audit §H |

**Núcleo texto agregado: 99.7 %.**
El 0.3 % faltante corresponde a la cobertura nominal del nombre
`NEEDS_ENVIRONMENT` como test paramétrico exclusivo (vive como rama
verificada en `test_vision_without_vlm.py` y como rama indirecta de la
matriz, no como fila propia de la matriz). No es brecha funcional.

---

## 3. Qué quedó cerrado

- **Identidad y trivial:** `quién eres`, `hola`, `ok`, `a`, `qué?`,
  `gracias`, frustración → `mission_status=trivial`, terminal
  `DIRECT_CHAT`, sin tools, sin GUI.
- **Status público estructural:** `compute_mission_status` decide
  exclusivamente desde `tool_calls_made + verifier_results +
  policy_blocks + engine_errors`. El texto del LLM no participa.
- **Honestidad:** `_normalize_tool_result_evidence` degrada
  `ok=True` sin evidencia + verifier `confirmed/skipped` a
  `ToolResult.ok=False` + `VerifiedOutcome.status=unverifiable`.
- **Trazabilidad:** `turn_state_sequence` en `last_turn_trace` con
  estados canónicos `RECEIVED_INPUT`, `CLASSIFYING_INTENT`,
  `PLANNING_TOOL_USE`, `EXECUTING_TOOL`, `VERIFYING`,
  `OBSERVING_SCREEN`, `GUI_PLANNING`, `GUI_ACTING`,
  `VERIFYING_SCREEN`, `NEEDS_PERMISSION`, `NEEDS_ENVIRONMENT`,
  `COMPLETED`, `PARTIAL_WITH_NEXT_STEP`, `FAILED`, `NEEDS_USER`,
  `UNVERIFIED`, `DIRECT_CHAT`.
- **App resolver universal:** `psutil` + `Get-StartApps` + `rapidfuzz
  ≥ 85`. Cero hardcodes por marca.
- **App open / close verificados** con `ProcessProbe` / `WindowProbe`
  y retry honesto.
- **Filesystem write** verifica `exists` + `content`; empty result no
  cierra `complete`.
- **Terminal** reporta `stdout`, `stderr`, `exit_code`, `timeout`,
  excepciones, sin fake success.
- **Verifier** distingue `confirmed`, `failed`, `skipped`,
  `unverifiable`, `pending`.
- **GUI / percepción on-demand:** chat / identity / knowledge /
  trivial / memory / style **no** disparan screenshot, UIA, OCR ni
  VLM. `gui_click` / `gui_type` son `RiskLevel.HIGH` y requieren
  permission. `gui_action` sin readback ⇒ `UNVERIFIED`.
- **Contratos `ScreenObservation` / `OCRProvider` /
  `OCRUnavailableProvider`:** vivos, frozen, testeados, sin provider
  real activo (correcto para esta fase).
- **Cero hardcodes:** `audit/hardcode_guard.py` clean (56 files).

---

## 4. Qué sigue pendiente (backlog honesto, no bloqueante)

Ver [`TEXT_CORE_100_MASTER_PLAN.md`](TEXT_CORE_100_MASTER_PLAN.md) §9.
Resumen:

- BK-1 OCR real (Tesseract / Paddle).
- BK-2 `image_diff` perceptual ligero.
- BK-3 MSAA fallback para Electron / CEF.
- BK-4 Conectar `ScreenObservation` al verifier como evidencia normalizada.
- BK-5 `ScreenshotProvider` que devuelva `ScreenObservation`.
- BK-6 GUI real con readback (UIA delta + window state delta).
- BK-7 VLM local opt-in.
- BK-8 Voz (STT / TTS).
- BK-9 Browser avanzado / Playwright.
- BK-10 UI / HUD / overlay.
- BK-11 Marketplace de skills.
- BK-12 Cold-start mitigation (preload, keep_alive, spinner launcher).
- BK-13 Tests nominales T1 / T2 / T3 (cobertura cosmética).

Adicional, heredado de Carter v2 (`RESIDUAL.md`):

- R-V2-B1 Action-route fallback ya implementado en v3
  (`test_action_route_synthesises_app_open_when_llm_silent`).
- R-V2-B2 Detector estructural de declarative-fact: cubierto a nivel
  contrato (D3) e implementado para casos básicos.
- R-V2-B3 Cold-start residual del primer turno (queda en backlog
  launcher).
- R-V2-B4 `que?` y entradas ambiguas mono-token: cubiertas por
  `test_low_info_input_returns_trivial`.
- R-V2-B5 Recovery classifier: v3 nunca lo portó (decisión D5/D10).
- R-V2-B6 Dry-run no es evidencia live: respetado.
- R-V2-B7 Cases del transcript real: mapeados, los relevantes pasan.

---

## 5. Bugs corregidos en esta pasada

**Cero.** No se detectó ningún bug que justificara cambio de código.
La regla del prompt era explícita: "Si no encuentras bugs de lógica,
no inventes cambios". Confirmado.

---

## 6. Tests agregados en esta pasada

**Cero.** La cobertura existente (398 tests + hardcode_guard) ya
satisface la DoD. La regla del prompt aceptaba "agregar tests /
documentación y decirlo": en este caso lo correcto fue **documentar y
no inflar la suite**, dado que cada test mandado por el prompt ya
tiene equivalente verde:

| Test mandado por el prompt (Fase 6) | Equivalente vivo |
|---|---|
| `hola` no llama tools | `test_greeting_does_not_run_resolver`, `test_trivial_input_does_not_call_tools` |
| `ok` no llama tools | `test_trivial_input_does_not_call_tools` |
| `a` no llama tools | `test_trivial_input_does_not_call_tools`, `test_low_info_input_returns_trivial` |
| `qué?` no llama tools | `test_question_returns_trivial_no_tools` |
| `gracias` no llama tools | `test_trivial_input_does_not_call_tools` |
| identity sin tools | `test_identity_text_ignores_spurious_tool_call`, `test_identity_can_say_carter_even_if_window_title_contains_carter` |
| frustración no dispara acción | `test_force_kill_wording_does_not_synthesise_app_tool` |
| active window no contamina | `test_active_app_contamination_guard_in_chat_route`, `test_potential_followup_still_blocks_active_app_contamination` |
| empty ok tool result no completed | `test_empty_ok_tool_result_is_not_treated_as_completed` |
| dispatcher exception no success | `test_dispatcher_exception_does_not_report_success` |
| confirmed sin evidencia → unverified | `test_confirmed_without_evidence_is_downgraded_to_unverified` |
| skipped completes solo si semánticamente válido | `test_skipped_verifier_can_still_finish_completed_without_fake_success` |
| partial → partial_with_next_step | `test_partial_mission_uses_partial_with_next_step_terminal_state` |
| matriz MissionStatus | `test_mission_status_terminal_trace_matrix` (paramétrica) |
| `turn_state_sequence` existe | `test_trace_exposes_canonical_turn_states` |
| app resolver exact / case-insens / typo | `test_app_resolver.py` + `test_app_open_verifier.py` + `test_typo_target_resolves_via_resolver` |
| app_open verified / unverified | `test_app_open_pending_retries_once_and_succeeds`, `test_app_open_pending_retries_once_and_stays_unverified` |
| app_close ambiguous | `test_ambiguous_open_does_not_reopen_recent_close` |
| high-risk app needs permission | `test_llm_user_approved_flag_does_not_execute_high_risk_tool`, `test_human_confirmation_executes_pending_high_risk_tool` |
| filesystem write evidence | `test_filesystem_dispatch.py::fs_write_verifier_needs_evidence_not_empty_stub` |
| read missing file honest | `test_filesystem_dispatch.py` (rama de error) |
| terminal stdout / stderr / exit_code / timeout | `test_terminal_dispatch.py` |
| destructive blocked | `test_destructive_input_blocked_to_failed`, `test_format_drive_blocked` |
| chat no dispara screenshot / UIA / OCR / VLM | `test_simple_chat_inputs_never_activate_screen_or_gui`, `test_vision_without_vlm.py` (paramétrico) |
| explicit screenshot route emits OBSERVING / VERIFYING | `test_explicit_screenshot_route_emits_observing_and_screen_states` |
| gui_click / gui_type require permission | `test_gui_high_risk_requires_permission_and_traces_needs_permission` |
| gui sin readback → UNVERIFIED | `test_gui_action_without_external_readback_ends_unverified_with_approval` |
| ScreenObservation / OCRUnavailable contracts | `tests/test_vision_without_vlm.py` (16 tests específicos) |
| VLM not selected | `test_vision_without_vlm.py::vlm_jamás_se_elige_para_safe_kinds` |

Conclusión: **agregar tests duplicados habría inflado la suite sin
ganancia real**. Los tests ya cubren el contrato.

---

## 7. Tests corridos en esta pasada

```powershell
$env:PYTHONPATH = "src"
python -m pytest --tb=short
# → 398 passed in 145.23s (0:02:25)

python audit/hardcode_guard.py
# → hardcode_guard: clean (56 files scanned)
```

Subsets relevantes (corroborados en pasadas previas y aún verdes):

- Mark-inspired text core: 6 / 6 PASS.
- Second pass hardening: 6 / 6 + 127 / 127 (suites laterales) PASS.
- MissionStatus matrix (Third pass): 8 / 8 PASS.
- GUI perception (Third pass): 19 / 19 PASS.
- Vision Without VLM: 22 / 22 PASS + 15 / 15 (subset gating) PASS +
  154 / 154 (suites laterales) PASS + 398 / 398 (full).

---

## 8. Resultado de suite completa

| Métrica | Valor |
|---|---|
| Tests recolectados | 398 |
| Pass | 398 |
| Fail | 0 |
| Skip | 0 |
| Tiempo | 145.23 s (≈ 2 min 25 s) |
| Hardcode guard | clean (56 files scanned) |

Sin tests ocultados, sin tests deselected, sin xfails, sin
warnings nuevos.

---

## 9. Resultado de live-safe

**No ejecutado** en esta pasada. El plan documentado vive en
[`LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md`](LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md).

Razones honestas:

1. Requiere Ollama corriendo y el agente no controla ese proceso.
2. Algunos casos abren / cierran apps reales (Notepad) y requieren
   confirmación del usuario.
3. La cobertura scripted (398 / 398) cubre el comportamiento lógico
   de cada caso del smoke; la diferencia es runtime real (latencia,
   modelo, OS), que es exactamente lo que el plan está diseñado para
   verificar manualmente.

Recomendación al usuario: ejecutar el smoke después de un cold-start
limpio del PC; capturar evidencia por caso según §7 del plan.

---

## 10. Riesgos restantes

Ver [`TEXT_CORE_100_MASTER_PLAN.md`](TEXT_CORE_100_MASTER_PLAN.md) §10.
Resumen:

- **R1** Regresión silenciosa de la matriz paramétrica de `MissionStatus`
  (mitigado: test vivo + DoD).
- **R2** Que se agregue VLM o cloud por error (mitigado:
  `hardcode_guard` + test `vlm_jamás_se_elige`).
- **R3** Que se relaje `gui_click` / `gui_type` a `MEDIUM` para "que
  pase tests" (mitigado: test específico).
- **R4** Consumidor que asuma lista cerrada de `turn_state_sequence`
  (documentado como extensible).
- **R5** Cold-start del primer turno sin Ollama listo
  (`RESIDUAL.md` R-V2-B3, mitigación en backlog launcher).

Ninguno bloquea el cierre del núcleo texto.

---

## 11. Backlog explícito (post-cierre)

Idéntico a [`TEXT_CORE_100_MASTER_PLAN.md`](TEXT_CORE_100_MASTER_PLAN.md) §9.
**Ningún item del backlog es requisito para considerar el núcleo
texto como cerrado.**

---

## 12. Veredicto honesto

# **TEXT_CORE_READY**

Justificación punto por punto contra el criterio de éxito del prompt:

| Criterio | Cumplido | Evidencia |
|---|---|---|
| Suite relevante pasa | ✅ | 398 / 398 (incluye agent integration, terminal, filesystem, verifier, resolver, security, app, perception, uia, vision-without-vlm) |
| Suite completa pasa | ✅ | `pytest` → 398 / 398 in 145.23 s |
| No hay fake success conocido | ✅ | `_normalize_tool_result_evidence` + `compute_mission_status` estructural + tests B |
| Conversación simple no usa tools | ✅ | tests A1 – A9 verdes |
| `MissionStatus` mapping cubierto | ✅ | matriz paramétrica `test_mission_status_terminal_trace_matrix` verde |
| GUI / percepción no se activa indebidamente | ✅ | `test_simple_chat_inputs_never_activate_screen_or_gui` paramétrico verde |
| App / filesystem / terminal con tests relevantes | ✅ | suites verdes, hardcode_guard 0 / 0 |
| Hay smoke plan o smoke real | ✅ | `LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md` documentado con 6 secciones y 19 casos |
| Riesgos restantes no bloquean el núcleo texto | ✅ | R1 – R5 mitigados / aceptados |

---

## 13. Próximo paso recomendado

1. **Ejecutar el smoke live-safe** (Sección 8 del prompt original)
   contra Ollama real, con `qwen3:8b` o equivalente, registrando
   evidencia por caso. Si todos pasan, el cierre se confirma
   empíricamente; si alguno falla, abrir mini-pasada con bug
   reproducible.
2. **Iniciar la siguiente fase** según prioridad declarada por el
   usuario:
   - Voz (BK-8) si el siguiente objetivo es voz local privada;
   - Browser avanzado (BK-9) si el siguiente objetivo es web real;
   - GUI real con readback (BK-6) si el siguiente objetivo es Jarvis
     visual texto;
   - Cold-start mitigation (BK-12) si el siguiente objetivo es UX de
     latencia.
3. **No abrir VLM ni OCR real ni cloud** hasta que el usuario lo
   pida explícitamente. Están fuera de alcance por contrato.

---

## 14. Cierre

El núcleo texto de Carter v3 ha alcanzado un estado **consolidado,
verificable y honesto** bajo la Definition of Done definida en esta
pasada. La evidencia es reproducible (398 / 398 + hardcode_guard
limpio) y los riesgos restantes están documentados sin maquillaje.

Carter está listo para que la siguiente fase (voz, GUI real, browser,
o lo que el usuario decida) se construya **encima** de este núcleo,
no **dentro** de él.

— Pasada **TEXT_CORE_CLOSURE_FINAL** completada.
