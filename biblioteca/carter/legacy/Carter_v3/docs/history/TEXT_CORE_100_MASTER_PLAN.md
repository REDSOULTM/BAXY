# TEXT_CORE_100_MASTER_PLAN

> Pasada: **TEXT_CORE_CLOSURE_FINAL** — Fase 4 (plan maestro).
> Modelo/rol: Opus 4.7 Medium.
> Documento dependiente: [`TEXT_CORE_CLOSURE_AUDIT.md`](TEXT_CORE_CLOSURE_AUDIT.md).

Este es el plan maestro para llevar Carter v3 a "100 % núcleo texto"
bajo la Definition of Done de §I del audit. **No** es un roadmap de
features. **No** abre fases nuevas (voz, cámara, VLM, UI/HUD).

---

## 1. Estado actual estimado por área (porcentaje honesto)

Porcentajes calculados **solo** contra la Definition of Done de §I del
audit, ponderando: implementación + test específico + ausencia de
deuda conocida. No incluyen futuras pasadas.

| Área | % | Justificación |
|---|---|---|
| Núcleo texto conversacional | **100 %** | Todos los checkboxes I.1 verdes. |
| Anti fake-success / honestidad | **100 %** | Todos los checkboxes I.2 verdes; status estructural. |
| Trazabilidad / estados internos | **98 %** | I.3 verde; el 2 % faltante es un test paramétrico nominal de `NEEDS_ENVIRONMENT` (cobertura indirecta hoy). |
| Apps / procesos / app_open / app_close | **100 %** | I.4 verde; cero hardcodes por marca. |
| Filesystem | **100 %** | I.5 verde. |
| Terminal | **100 %** | I.6 verde. |
| Verifier | **100 %** | I.7 verde. |
| GUI / percepción on-demand básica sin VLM | **100 %** | I.8 verde; 22 tests anti-regresión. |

**Núcleo texto agregado:** ≈ **99.7 %**.

---

## 2. Brechas restantes

Las brechas son menores y todas residen en **cobertura nominal** o en
**limitaciones aceptadas y documentadas**, no en lógica rota.

| ID | Brecha | Severidad | Decisión |
|---|---|---|---|
| G1 | `NEEDS_ENVIRONMENT` no tiene test paramétrico exclusivo (vive en `test_vision_without_vlm.py` y matriz indirecta) | Baja | "Solo testear ahora" — opcional. No bloquea cierre. |
| G2 | `gui_click` / `gui_type` siguen siendo stubs que sin readback externo cierran `UNVERIFIED` | Baja | Diseño correcto bajo Valor 4. Backlog si una pasada futura quiere readback real. |
| G3 | `OCRUnavailableProvider` no se inyecta como default en ningún consumidor | Baja | Esperado: el contrato existe para futuros providers. Backlog. |
| G4 | `ScreenObservation` no se usa todavía en `verifier`/`dispatch` | Baja | Esperado, helper opt-in. Backlog. |
| G5 | Cold-start de Ollama puede exceder 8 s en primer turno (ver `RESIDUAL.md` R-V2-B3) | Baja | Mitigación: `keep_alive=10m` + preload en launcher. Vive en backlog de FASE 1 / 4. |
| G6 | Apps Electron / CEF exponen árboles UIA pobres | Baja | Documentado en `VISION_WITHOUT_VLM_REPORT.md` §12. Backlog: MSAA fallback. |

---

## 3. Bugs conocidos

**Cero bugs conocidos** en el núcleo texto. La suite 398 / 398 verde y
`hardcode_guard` 0 / 0 lo respaldan. Cualquier "bug" reportado a partir
de aquí debe aparecer primero como test rojo reproducible.

---

## 4. Tests faltantes (no bloqueantes)

| ID | Test sugerido | Prioridad |
|---|---|---|
| T1 | `test_needs_environment_terminal_state_for_uia_unavailable` (paramétrico dedicado) | Opcional |
| T2 | `test_terminal_empty_stdout_with_zero_exit_does_not_complete_when_no_evidence` (nombre largo, lógica ya cubierta indirectamente) | Opcional |
| T3 | `test_app_close_does_not_close_unrelated_window_when_target_unresolved` (cobertura nominal de wrong-window) | Opcional |

Ninguno bloquea el cierre. Todos pueden quedar como backlog inmediato
para una mini-pasada futura sin riesgo.

---

## 5. Fixes mínimos necesarios

**Cero fixes necesarios** para cerrar la Definition of Done. Ver §3.

---

## 6. Qué NO se debe tocar

- `agent.py`: no reescritura completa.
- `contracts.py`: `MissionStatus` (6 valores), `TERMINATION_REASONS`
  frozenset, `VerifierStatus` (5 valores), `compute_mission_status`
  estructural — **bloqueado por contrato público**.
- `tools/catalog.py`: niveles de riesgo de `gui_click` / `gui_type`
  (siguen `RiskLevel.HIGH`).
- `tools/verifier.py`: `gui_action` sigue cerrando `UNVERIFIABLE` sin
  readback externo.
- `perception/observation.py` / `perception/ocr.py`: contratos frozen,
  no se mutan en runtime.
- Lista de hardcodes: `audit/hardcode_guard.py` debe seguir verde.
- Cualquier dependencia nueva (sin `rapidfuzz` extra, sin Tesseract,
  sin Playwright, sin VLM, sin Gemini).

---

## 7. Orden recomendado (para esta pasada)

1. **Documentación** — generar los 5 documentos de la fase
   (master_context, audit, master_plan, smoke_plan, closure_report).
   *(ESTA PASADA)*
2. **Validación reproducible** — correr suite completa + hardcode_guard
   y dejar evidencia en el reporte. *(ESTA PASADA)*
3. **Smoke plan live-safe** — escribir
   `LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md` con casos exactos. La ejecución
   real del smoke depende del usuario (Ollama corriendo + decisión de
   ejecutar). *(ESTA PASADA, sin ejecución obligatoria)*
4. **Cierre formal** — emitir veredicto en
   `TEXT_CORE_CLOSURE_REPORT.md`. *(ESTA PASADA)*
5. **Backlog** — todo lo de §4 y §8 entra como mini-pasadas
   independientes futuras.

---

## 8. Criterio de cierre por área

Cada área cierra cuando:

| Área | Criterio cierre |
|---|---|
| A — Conversación | Todos los tests de I.1 verdes (✓ hoy). |
| B — Honestidad | Todos los tests de I.2 verdes (✓ hoy). |
| C — Trazabilidad | Matriz paramétrica `mission_status_terminal_trace_matrix` verde (✓ hoy). |
| D — Apps | `test_app_resolver.py`, `test_app_open_verifier.py` verdes + `hardcode_guard` 0 / 0 (✓ hoy). |
| E — Filesystem | `test_filesystem_dispatch.py` verde con verificación de evidencia no vacía (✓ hoy). |
| F — Terminal | `test_terminal_dispatch.py` verde + estructural shape test (✓ hoy). |
| G — Verifier | `test_verifier.py` + `test_verifier_actions.py` verdes (✓ hoy). |
| H — GUI/percepción | 22 tests de `test_vision_without_vlm.py` + tests gating de `test_agent_integration.py` verdes (✓ hoy). |

Suite completa **398 / 398** verde y `hardcode_guard` **clean (56 files
scanned)** lo confirman.

---

## 9. Backlog (fuera de esta fase)

| ID | Item | Bloque |
|---|---|---|
| BK-1 | Implementar `OCRProvider` real (Tesseract / Paddle) | OCR real |
| BK-2 | `image_diff` perceptual ligero | Percepción |
| BK-3 | MSAA fallback para Electron / CEF en `UiaProbe` | UIA |
| BK-4 | Conectar `ScreenObservation` a `verifier` y `dispatch` como evidencia normalizada | Observabilidad |
| BK-5 | `ScreenshotProvider` que devuelva `ScreenObservation(source=screenshot, …)` | Percepción |
| BK-6 | `gui_click` / `gui_type` con readback real (UIA post-acción + delta de ventana) | GUI real |
| BK-7 | VLM local opcional gateado por env-var explícito | VLM |
| BK-8 | Voz / STT / TTS (faster-whisper, piper) | Voz |
| BK-9 | Browser avanzado / Playwright | Web |
| BK-10 | UI / HUD / overlay | UX |
| BK-11 | Marketplace de skills | Plataforma |
| BK-12 | Cold-start mitigation (`keep_alive`, preload, spinner launcher) | Latencia |
| BK-13 | Tests T1 / T2 / T3 de §4 | Cobertura nominal |

---

## 10. Riesgos

| ID | Riesgo | Mitigación |
|---|---|---|
| R1 | Que una futura pasada borre la matriz paramétrica de `MissionStatus` y deje regresar fake success | Test parametrizado vivo + DoD de §I del audit como contrato. |
| R2 | Que se agregue VLM o cloud por error | `audit/hardcode_guard.py` + `test_vision_without_vlm.py::vlm_jamás_se_elige` lo bloquean. |
| R3 | Que se relaje `gui_click` / `gui_type` a `MEDIUM` para "que pase tests" | Test específico `test_gui_high_risk_requires_permission_and_traces_needs_permission` rompe si pasa. |
| R4 | Que un consumidor lea `last_turn_trace` esperando estados que no existen | `turn_state_sequence` documentada como extensible; consumidor no debe asumir lista cerrada. |
| R5 | Que el cold-start del primer turno sin Ollama listo se reporte como "Carter es lento" | `RESIDUAL.md` R-V2-B3 + smoke plan documentan que requiere `ollama serve` previo. |

---

## 11. Distinción "Implementar / Solo testear / Backlog / Rechazar"

| Categoría | Items | Acción esta pasada |
|---|---|---|
| **Implementar ahora** | (ninguno) | — |
| **Solo testear ahora** | Suite completa + hardcode_guard + smoke plan documentado | Hecho en Fase 7 + 8 |
| **Backlog** | BK-1 … BK-13 + T1 / T2 / T3 | Documentado |
| **Rechazar** | VLM activo, voz, cámara, OCR real, browser avanzado, UI/HUD, marketplace, generated_code | Documentado |

---

## 12. Veredicto del plan

El núcleo texto **no requiere implementación adicional** para alcanzar
la Definition of Done. La acción única que queda es **firmar el cierre**
con evidencia reproducible, lo cual se hace en
[`TEXT_CORE_CLOSURE_REPORT.md`](TEXT_CORE_CLOSURE_REPORT.md).
