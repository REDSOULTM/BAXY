# TEXT_CORE_MASTER_CONTEXT

> Pasada: **TEXT_CORE_CLOSURE_FINAL** (cuarta y última pasada de la fase texto).
> Modelo/rol: Opus 4.7 Medium, auditor + implementador.
> Conversación nueva — todo el estado a continuación viene de releer los
> documentos del repo, no de memoria de chat.

Este documento existe para que cualquier agente futuro entienda, en una sola
lectura, qué es Carter, qué se ha cerrado en el núcleo texto, qué aportó Mark,
qué se rechazó, y qué queda explícitamente fuera de alcance hasta que el
núcleo texto esté firmado.

---

## 1. Qué es Carter (según `ContextoCarter.md`)

Carter es un **asistente personal local tipo Jarvis** que vive en el PC del
usuario. La fuente de verdad absoluta es
[ContextoCarter.md](../ContextoCarter.md). Sus once valores resumidos son:

1. **Local-first y privado** — sin nube obligatoria, sin telemetría, sin
   enviar pantalla/voz/archivos por defecto.
2. **Rápido** — chat trivial 3–5 s ideal / 8 s máximo; el overhead pre-LLM
   debe ser mínimo.
3. **No miente nunca** — `COMPLETED` solo con evidencia; estados honestos:
   `PARTIAL_WITH_NEXT_STEP`, `NEEDS_USER`, `NEEDS_ENVIRONMENT`,
   `NEEDS_PERMISSION`, `UNVERIFIED`, `BLOCKED_BY_POLICY_WITH_SAFE_ALTERNATIVE`.
4. **Verifica lo que hace** — toda acción con efecto debe tener readback;
   sin readback ⇒ `UNVERIFIED`.
5. **Falla bien sin rendirse fácil** — recupera antes de declarar fallo, sin
   loops infinitos.
6. **Universal, no hardcodeado** — funciona por intención y resolución de
   recursos reales, no por listas de frases/marcas.
7. **Sin hacks por app** — nada de `if Steam`, `if YouTube`, `if WhatsApp`
   en el core.
8. **No depende de un solo modelo** — perfiles por VRAM (CPU-only … 24 GB+),
   ≤80–85 % VRAM total.
9. **Maneja modelos con justicia** — protocolo correcto por familia, sin
   `if model == "qwen"`.
10. **Texto antes que voz** — la voz/cámara serán capas encima del núcleo
    texto, nunca rutas paralelas.
11. **Inputs triviales rápidos y seguros** — `a`, `ok`, `qué?`, `nada`,
    `gracias`, frustración no deben activar tools/GUI/screen.

Esa visión manda sobre cualquier auditoría, plan o reporte posterior.

---

## 2. Qué áreas se han trabajado hasta ahora

Carter v3 nació como reescritura limpia desde Carter v2, en rondas
documentadas (`V2_IMPORT_ROUND_1_LOG.md` … `V2_IMPORT_ROUND_15_LOG.md`).
Las áreas trabajadas, en orden cronológico:

| Pasada / Ronda | Área | Estado al cierre |
|---|---|---|
| Rondas 1 – 15 (V2→V3 import) | base, resolver, dispatch, terminal, filesystem, security, perception, GUI stubs | importado, suite verde |
| Mark-inspired text core | trazabilidad de turno + anti fake-success | cerrado |
| Second pass text-core hardening | `PARTIAL_WITH_NEXT_STEP` terminal real, fix indentación `_matching_process_names`, evidencia vacía no completa | cerrado |
| Third pass — MissionStatus trace | matriz paramétrica `MissionStatus → terminal_state` | cerrado |
| Third pass — GUI / perception | estados `OBSERVING_SCREEN` / `GUI_PLANNING` / `GUI_ACTING` / `VERIFYING_SCREEN`, `gui_click`/`gui_type` ⇒ `RiskLevel.HIGH`, `gui_action` sin readback ⇒ `UNVERIFIABLE` | cerrado |
| Vision Without VLM | contratos `ScreenObservation` / `OCRProvider` / `OCRUnavailableProvider`, 22 tests anti-regresión, ladder bloqueado en `INTERNAL` para chat | cerrado |
| **Esta pasada (TEXT_CORE_CLOSURE_FINAL)** | auditoría, DoD, plan maestro, smoke plan y reporte final de cierre | **cierre** |

Documentos asociados, todos vivos:

- `AUDIT_MARK_TO_CARTER_TEXT_CORE.md`, `PLAN_MARK_INSPIRED_TEXT_CORE.md`,
  `MARK_TO_CARTER_TEXT_CORE_REPORT.md`
- `SECOND_PASS_TEXT_CORE_HARDENING_PLAN.md`,
  `SECOND_PASS_TEXT_CORE_HARDENING_REPORT.md`
- `THIRD_PASS_MISSION_STATUS_TRACE_REPORT.md`
- `THIRD_PASS_GUI_PERCEPTION_AUDIT.md`,
  `THIRD_PASS_GUI_PERCEPTION_PLAN.md`,
  `THIRD_PASS_GUI_PERCEPTION_REPORT.md`
- `VISION_WITHOUT_VLM_AUDIT.md`, `VISION_WITHOUT_VLM_PLAN.md`,
  `VISION_WITHOUT_VLM_REPORT.md`
- `CHANGELOG.md`, `RESIDUAL.md`

---

## 3. Qué aportó Mark y qué se rechazó

**Tomado (adaptado, sin pegado literal):**

- Idea de **estado/progreso operacional explícito por turno** ⇒ secuencia
  canónica de estados internos (`turn_state_sequence`) en
  `src/carter_v3/trace.py`, sin UI/voz.
- Idea de **endurecer ejecución para evitar éxito optimista** ⇒
  `_normalize_tool_result_evidence` en `src/carter_v3/agent.py` y
  degradación de `confirmed sin evidencia` a `UNVERIFIED`.
- Idea de **plan → acción → verificación** como capas explícitas en
  GUI/percepción ⇒ estados `OBSERVING_SCREEN` / `GUI_PLANNING` /
  `GUI_ACTING` / `VERIFYING_SCREEN` y `gui_action` sin readback externo
  ⇒ `UNVERIFIABLE`.

**Rechazado explícitamente** (cubierto por `ContextoCarter.md` y
`MARK_TO_CARTER_TEXT_CORE_REPORT.md`):

- Dependencia obligatoria a Gemini / cloud / otro LLM.
- `generated_code` o `exec` dinámico.
- Respuesta `"Done"` por defecto.
- Browser Playwright avanzado.
- File processor universal con cloud.
- Hardcodes por marca (`if Steam` / `if YouTube` / `if WhatsApp`).
- Drag & drop, voz, cámara física, UI/HUD, marketplace.
- Reescritura completa de `agent.py` (no se hizo).
- Cambio del contrato público `MissionStatus` a más de 6 valores.

---

## 4. Qué se cerró en anti fake-success

Cubierto por la **primera pasada Mark-inspired** y reforzado en la
**segunda pasada hardening**:

- `_normalize_tool_result_evidence` en `src/carter_v3/agent.py`: una tool
  de acción que devuelve `ok=True` sin `message` ni `data` y un verifier
  `confirmed/skipped` se degrada a `ToolResult.ok=False`,
  `message="tool_returned_ok_without_evidence"`,
  `VerifiedOutcome.status=unverifiable`.
- Excepciones del dispatcher no terminan en `COMPLETED`
  (`test_dispatcher_exception_does_not_report_success`).
- `verifier confirmed sin evidencia` ⇒ `UNVERIFIED`
  (`test_confirmed_without_evidence_is_downgraded_to_unverified`).
- `verifier skipped` puede completar si la semántica lo permite, pero
  nunca por defecto sin evidencia
  (`test_skipped_verifier_can_still_finish_completed_without_fake_success`).
- `verifier failed` mapea a `failed`; `unverifiable` mapea a `unverified`.
- `compute_mission_status` (`src/carter_v3/contracts.py`) es estructural:
  el texto del LLM no participa en el cálculo del status público.
- Reply composer (`src/carter_v3/response_composer.py`) no inyecta
  palabras de éxito sin evidencia
  (`test_unverified_action_reply_is_evidence_based`).

---

## 5. Qué se cerró en MissionStatus / `turn_state_sequence`

Cubierto por la **tercera pasada (MissionStatus trace)** y blindado por
la **pasada Vision Without VLM**:

- `MissionStatus` público está pinneado en 6 valores: `trivial`,
  `complete`, `partial`, `failed`, `needs_user`, `unverified`
  (`src/carter_v3/contracts.py:21-37`, `PUBLIC_MISSION_STATUSES`
  frozenset).
- `TERMINATION_REASONS` es un frozenset cerrado validado en
  `AgentTurnResult.__post_init__`.
- `turn_state_sequence` se proyecta en `last_turn_trace`
  (`src/carter_v3/trace.py`) e incluye los estados terminales canónicos:
  `COMPLETED`, `PARTIAL_WITH_NEXT_STEP`, `FAILED`, `NEEDS_USER`,
  `UNVERIFIED`, `DIRECT_CHAT`.
- Estados internos exclusivos de GUI/percepción: `OBSERVING_SCREEN`,
  `GUI_PLANNING`, `GUI_ACTING`, `VERIFYING_SCREEN`, `NEEDS_PERMISSION`,
  `NEEDS_ENVIRONMENT`. Nunca se filtran a `mission_status`.
- Matriz paramétrica `test_mission_status_terminal_trace_matrix`
  (`tests/test_agent_integration.py`) cubre los 7 mapeos `mission_status
  + termination_reason → terminal_state`.

---

## 6. Qué se cerró en GUI / percepción on-demand

Cubierto por la **tercera pasada GUI/percepción**:

- Chat / identidad / knowledge / trivial / memory / style **nunca**
  activan screenshot, UIA, OCR ni VLM
  (`test_simple_chat_inputs_never_activate_screen_or_gui`,
  `test_active_app_contamination_guard_in_chat_route`,
  `test_potential_followup_still_blocks_active_app_contamination`).
- Ladder de percepción `INTERNAL → PROCESS → WINDOW_UIA → SYSTEM_API
  → WEB_AUTOMATION → SCREENSHOT → OCR → VLM` se queda en `INTERNAL`
  para esas rutas.
- `gui_click` / `gui_type` registrados como `RiskLevel.HIGH` ⇒ requieren
  aprobación del `PolicyEngine`
  (`test_gui_high_risk_requires_permission_and_traces_needs_permission`).
- `gui_action` con `ok=True` pero sin readback externo ⇒ `UNVERIFIABLE`
  (`test_gui_action_without_external_readback_ends_unverified_with_approval`).
- Ruta `desktop_screenshot` real (PowerShell + System.Drawing) con
  verificación de existencia + tamaño; emite `OBSERVING_SCREEN` y
  `VERIFYING_SCREEN`
  (`test_explicit_screenshot_route_emits_observing_and_screen_states`).

---

## 7. Qué se cerró en Vision Without VLM

Cubierto por la **pasada Vision Without VLM** (cuarta pasada técnica):

- Contrato común inmutable `ScreenObservation` / `UIElementObservation`
  / `EvidenceFragment` en `src/carter_v3/perception/observation.py`.
- Skeleton `OCRProvider` / `OCRResult` / `OCRUnavailableProvider` en
  `src/carter_v3/perception/ocr.py`. `available=False` ⇒ `text` debe
  estar vacío (defensa anti fake-success).
- 22 tests en `tests/test_vision_without_vlm.py` que blindan:
  ladder no escala fuera de chat, `ScreenObservation` rechaza valores
  inválidos, `OCRResult` con `available=False` no puede inventar texto,
  `MissionStatus` sigue en 6 valores.
- Re-export limpio en `src/carter_v3/perception/__init__.py`.

VLM **no está activo** en runtime. No hay provider real registrado.
`VLMProvider` solo existe como punto de extensión futuro.

---

## 8. Qué queda explícitamente fuera de alcance

Hasta que el núcleo texto esté firmado como cerrado, todo lo siguiente
**no se toca**:

- **Voz** (STT real, mic capture, hotword).
- **Cámara física** (webcam / video stream / face).
- **VLM** real (llava, qwen2.5vl, paligemma, gemini-vision, etc.).
- **OCR real** (tesseract, paddle) — solo el skeleton del contrato vive.
- **UI / HUD** (overlay, system tray rico, ventanas Carter).
- **Browser avanzado** (Playwright, scraping pesado, multi-tab nav).
- **Marketplace** de skills / plugins de terceros.
- **Drag & drop**.
- **`generated_code` / exec dinámico**.
- **Cloud LLM obligatorio** (Gemini, Claude, GPT como dependencia).
- **Otro LLM además del local Ollama** como dependencia core.
- **Cambios al contrato público** `MissionStatus` / `TERMINATION_REASONS`
  / `VerifierStatus` / `AgentTurnResult` salvo bug crítico justificado.

Estos puntos viven en el backlog de fases posteriores. Cualquier nueva
pasada debe respetarlos como restricción, no como invitación.

---

## 9. Estado heredado y notas de operación

- `git status` al inicio de esta pasada: rama `repo-cleanup-test-rebuild`,
  19 archivos modificados (parte de pasadas previas no commiteadas) y
  una larga lista de docs / artefactos de auditoría sin tracking. Esta
  pasada **no revierte ni borra** ninguno de esos cambios — los integra
  como estado actual.
- Comando para correr la suite (Windows / PowerShell):
  ```powershell
  $env:PYTHONPATH = "src"
  python -m pytest --tb=short
  ```
- Comando para hardcode guard:
  ```powershell
  python audit/hardcode_guard.py
  ```
- Baseline al inicio de esta pasada:
  - **pytest:** `398 passed in 145.23s (0:02:25)`.
  - **hardcode_guard:** `clean (56 files scanned)`.

Carter no necesita conexión a Ollama para que la suite pase: los tests
son scripted / mock; el smoke live-safe (Fase 8) requiere Ollama corriendo.

---

## 10. Para el próximo agente (resumen ultra-corto)

> El núcleo texto de Carter v3 está cerrado bajo la Definition of Done
> documentada en `TEXT_CORE_CLOSURE_AUDIT.md`. Suite 398/398, hardcode
> guard limpio. Los 6 valores públicos de `MissionStatus` están pinneados
> y los GUI/screen routes no se activan en chat trivial. La fase de voz,
> cámara, VLM, OCR real y UI/HUD está explícitamente fuera de alcance
> hasta que un nuevo prompt humano abra esa fase. Todo lo demás vive en
> `RESIDUAL.md`.
