# VISION_WITHOUT_VLM_REPORT

Pasada: **VISION_WITHOUT_VLM_FOUNDATION**
Fase: 5 — Reporte final.
Modo: Opus 4.7 Medium / pasada controlada.

> Documentos asociados:
> [VISION_WITHOUT_VLM_AUDIT.md](VISION_WITHOUT_VLM_AUDIT.md),
> [VISION_WITHOUT_VLM_PLAN.md](VISION_WITHOUT_VLM_PLAN.md).

---

## 1. Resumen ejecutivo

Carter ya tenía una base más sólida de la esperada para percepción de pantalla sin VLM gracias a la THIRD_PASS GUI Perception. Esta pasada **no agrega features nuevas**; cierra los tres huecos de **contrato y guard rails** que faltaban para que cualquier mejora futura (OCR real, image-diff, MSAA) se enchufe contra interfaces honestas y normalizadas:

1. Contrato común `ScreenObservation` (+ `UIElementObservation`, `EvidenceFragment`).
2. Skeleton OCR con `OCRProvider` / `OCRResult` / `OCRUnavailableProvider`.
3. Tests anti-regresión que pinan el gating (chat no activa pantalla) y el contrato público (`MissionStatus` sigue en 6 valores; `NEEDS_PERMISSION`/`NEEDS_ENVIRONMENT` solo viven como `termination_reason`).

Sin VLM. Sin LLM extra. Sin Gemini. Sin cloud. Sin OCR real instalado. Sin cámara. Sin voz. Sin UI/HUD. Sin Playwright. Sin browser visual. Sin `generated_code`. Sin hardcodes por app. Sin dependencias nuevas. Sin refactor.

**Veredicto:** `READY_TO_LAUNCH_TEXT_CORE_CLOSURE_FINAL` — ver §14.

---

## 2. Qué puede hacer Carter ahora sin VLM

(idéntico a antes de esta pasada; no se cambió comportamiento — solo se dejó documentado y testeado)

- **Procesos:** `ProcessProbe.names()` + `is_running()` con TTL 2s.
- **Ventanas:** `WindowProbe.windows()`/`titles()` con `process_name` por hwnd.
- **Foreground:** `window_list` + `UiaProbe.inspect_active_window()`.
- **UIA / accessibility tree:** `UiaProbe.list_windows`, `find_window`, `inspect_window`, `inspect_active_window`, `find_control` con snapshots que incluyen `bounding_rect`, `value`, `automation_id`, `control_type`, `is_enabled`, `is_offscreen`. Fallback honesto sin pywinauto.
- **Screenshot:** `desktop_screenshot(path)` real (PowerShell + System.Drawing) con verificación de existencia + tamaño.
- **GUI act:** `gui_click`/`gui_type` registrados como `RiskLevel.HIGH`, gateados por `PolicyEngine`, verificados por `gui_action` que devuelve `UNVERIFIABLE` sin readback externo.
- **Router de percepción:** ladder `INTERNAL → PROCESS → WINDOW_UIA → SYSTEM_API → WEB_AUTOMATION → SCREENSHOT → OCR → VLM` que en chat/identidad/knowledge/trivial/memory/style se queda en `INTERNAL`.
- **Estados internos:** `OBSERVING_SCREEN`, `GUI_PLANNING`, `GUI_ACTING`, `VERIFYING_SCREEN`, `NEEDS_PERMISSION`, `NEEDS_ENVIRONMENT`, `UNVERIFIED`, `PARTIAL_WITH_NEXT_STEP` — solo en rutas reales.
- **Honestidad:** sin readback externo, GUI termina `unverified`; sin captura, screenshot termina `failed`; sin pywinauto, UIA termina `unverifiable` con `needs_environment`.

---

## 3. Qué se implementó

### 3.1 CHANGE A — `ScreenObservation` contract (NEW)
[src/carter_v3/perception/observation.py](src/carter_v3/perception/observation.py)

- `EvidenceFragment` (frozen): `source`, `kind`, `payload`, `confidence`.
- `UIElementObservation` (frozen): `name`, `control_type`, `automation_id`, `value`, `bounds`.
- `ScreenObservation` (frozen): envelope normalizado con `source` validado contra `{uia, screenshot, ocr, process, window, composite}` y `verifier_status` validado contra `VERIFIER_STATUSES` público.
- `from_uia_inspection(inspection)`: helper opt-in que convierte un `UiaInspection` (duck-typed, sin import directo) a `ScreenObservation`. `None` → `UNVERIFIABLE` + `needs_environment=True` + `errors=("uia_unavailable",)`.

**No se enchufa todavía** a verifier/dispatch/agent. Queda disponible para futuros providers.

### 3.2 CHANGE B — OCR skeleton (NEW)
[src/carter_v3/perception/ocr.py](src/carter_v3/perception/ocr.py)

- `OCRResult` (frozen): `available`, `text`, `confidence`, `engine`, `error`, `needs_environment`. **Validación post-init**: `available=False` ⇒ `text` debe estar vacío (defensa anti fake-success).
- `OCRProvider` (Protocol): `name`, `is_available()`, `read_text(path)`.
- `OCRUnavailableProvider`: implementación por defecto. Siempre devuelve `available=False`, `needs_environment=True`, `engine="unavailable"`, `error="ocr_not_installed"`. Nunca lanza, nunca inventa texto.

**Cero dependencias externas**. **No se registra** como tool pública.

### 3.3 CHANGE C — Tests anti-regresión (NEW)
[tests/test_vision_without_vlm.py](tests/test_vision_without_vlm.py) — 22 tests:

1. Ladder no escala a SCREENSHOT/OCR/VLM para chat/identity/knowledge/trivial/memory/style (paramétrico).
2. `explicit_visual_request=True` sí entra en SCREENSHOT+ (regresión positiva).
3. VLM jamás se elige para 14 kinds "seguros".
4. `select_tools(perception_level=INTERNAL)` no incluye `desktop_screenshot` ni `gui_*`.
5. `select_tools(perception_level=SCREENSHOT)` sí incluye `desktop_screenshot`.
6. `ScreenObservation` rechaza `verifier_status` y `source` inválidos.
7. `ScreenObservation` defaults son vacíos / `PENDING`.
8. `EvidenceFragment` es inmutable (frozen).
9. `from_uia_inspection(None)` → `UNVERIFIABLE` + `needs_environment`.
10. `from_uia_inspection(insp)` con controles → `CONFIRMED` + UIElementObservations correctos.
11. `OCRUnavailableProvider().is_available() is False`.
12. `OCRUnavailableProvider.read_text` marca `needs_environment` y vacía `text`.
13. `OCRResult(available=False, text="leak")` lanza `ValueError`.
14. `OCRResult` es inmutable (frozen).
15. `PUBLIC_MISSION_STATUSES` sigue siendo exactamente los 6 valores fijados.
16. `needs_permission`/`needs_environment` son `termination_reason`, **no** `mission_status` público.

### 3.4 Re-export en `perception.__init__`
[src/carter_v3/perception/__init__.py](src/carter_v3/perception/__init__.py): se exportan los nuevos símbolos. No se modifica ningún símbolo existente.

---

## 4. Qué NO se implementó (y por qué)

| Idea (del prompt) | Decisión | Motivo |
|---|---|---|
| **CAMBIO D — image_diff básico** | NO | Aporte débil + presión por instalar PIL. Backlog hasta que un caso real lo justifique. |
| Auto-conversión `UiaInspection → ScreenObservation` en runtime | NO | Cambiaría comportamiento observable. Helper queda opt-in. |
| OCR real (Tesseract / Paddle) | NO | Requiere binario externo. Skeleton ya cubre el contrato. |
| MSAA fallback en UIA | NO | Solo si Electron/CEF se vuelve un blocker explícito. |
| Cualquier tool pública nueva (`screen_observe`, `ocr_read`, etc.) | NO | Aumentaría surface y arriesgaría el contrato público. |
| Exponer `NEEDS_PERMISSION` / `NEEDS_ENVIRONMENT` como `MissionStatus` | NO | Romperia el contrato público fijado en PARTE 1. Test de regresión añadido. |

---

## 5. Por qué NO se metió VLM

- **Fase actual:** núcleo texto + control de PC por texto. VLM es fase posterior.
- **Privacidad:** un VLM local always-on rompe el contrato local-first sin justificación. Un VLM cloud rompe el contrato local-first y suma latencia + dependencia.
- **Costo:** cualquier VLM utilizable hoy en local pide ≥ 8GB VRAM dedicada y latencia que destruye la velocidad en chat trivial.
- **No es necesario** para los casos comunes que Carter ya maneja: UIA + screenshot + (futuro) OCR + diff cubren la mayoría.
- **Honestidad:** prefiero `UNVERIFIED` o `NEEDS_ENVIRONMENT` antes que un "veo" alucinado por un modelo visual sin verificación causal.

---

## 6. Backlog (ordenado por valor / costo)

1. Implementar un `OCRProvider` real (Tesseract por defecto, Paddle alterno) cuando aparezca un caso de uso. Enchufarlo al ladder en nivel 6.
2. Implementar un `image_diff` minimal basado en hash perceptual ligero — solo como **evidencia débil** complementaria.
3. MSAA fallback en `UiaProbe` para apps Electron/CEF.
4. Conectar `ScreenObservation` al verifier para emitir evidencia normalizada en `VerifiedOutcome.evidence`.
5. Provider `ScreenshotProvider` que devuelva `ScreenObservation(source="screenshot", screenshot_path=..., evidence=...)`.
6. (Mucho más adelante) VLM local opcional gateado por env-var explícito + intent `screen_visual`.

---

## 7. Archivos modificados

- **NEW** [src/carter_v3/perception/observation.py](src/carter_v3/perception/observation.py)
- **NEW** [src/carter_v3/perception/ocr.py](src/carter_v3/perception/ocr.py)
- **EDITED** [src/carter_v3/perception/__init__.py](src/carter_v3/perception/__init__.py) (re-exports, no rompe nada)
- **NEW** [tests/test_vision_without_vlm.py](tests/test_vision_without_vlm.py) (22 tests)
- **NEW** [VISION_WITHOUT_VLM_AUDIT.md](VISION_WITHOUT_VLM_AUDIT.md)
- **NEW** [VISION_WITHOUT_VLM_PLAN.md](VISION_WITHOUT_VLM_PLAN.md)
- **NEW** [VISION_WITHOUT_VLM_REPORT.md](VISION_WITHOUT_VLM_REPORT.md)

Cero cambios en `agent.py`, `turn_support.py`, `contracts.py`, `tools/`, `request_patterns.py`, etc.

---

## 8. Tests agregados

22 tests en [tests/test_vision_without_vlm.py](tests/test_vision_without_vlm.py) (ver §3.3).

---

## 9. Tests corridos

| Suite | Comando | Resultado |
|---|---|---|
| Nuevos | `pytest tests/test_vision_without_vlm.py -v` | **22 passed** en 0.28s |
| Subset GUI/percepción/matrices | `pytest tests/test_agent_integration.py -k "simple_chat_inputs_never_activate_screen_or_gui or explicit_screenshot_route_emits_observing_and_screen_states or gui_high_risk_requires_permission_and_traces_needs_permission or gui_action_without_external_readback_ends_unverified_with_approval or mission_status_terminal_trace_matrix"` | **15 passed**, 92 deselected en 12.25s |
| Verifier / resolver / security / app / filesystem / terminal / perception / uia | `pytest tests/test_verifier.py tests/test_resolver.py tests/test_security.py tests/test_app_resolver.py tests/test_app_open_verifier.py tests/test_filesystem_dispatch.py tests/test_terminal_dispatch.py tests/test_perception.py tests/test_uia_probe.py` | **154 passed** en 6.27s |
| **Suite completa** | `pytest` | **398 passed** en 134.92s |

---

## 10. Resultados

- 0 regresiones.
- 0 tests modificados.
- 0 cambios de contrato público.
- 22 tests nuevos verdes.
- 398/398 tests verdes.

---

## 11. Riesgos restantes

- **GUI act real** sigue siendo stub — esto es deliberado y no toca esta pasada.
- `from_uia_inspection` no se invoca en runtime; si alguien lo conecta sin tests específicos, podría introducir conversión incorrecta — mitigado por los tests del helper.
- `OCRUnavailableProvider` no se inyecta como default en ningún sitio; si alguien implementa OCR real, debe asegurarse de que el provider sea sustituible sin romper callers (cubierto por el `Protocol`).

---

## 12. Limitaciones reales

- Apps Electron/CEF siguen exponiendo árboles UIA pobres → `inspect_window` puede devolver pocos controles.
- Sin OCR real instalado, **no** se puede leer texto rasterizado dentro de imágenes/canvas/PDFs.
- Sin `image_diff`, "se vio que algo cambió" sigue dependiendo de UIA + verificadores existentes.
- `desktop_screenshot` es Windows-only (PowerShell + System.Drawing); en otros OS responde honestamente `screenshot_supported_on_windows_only`.

---

## 13. Casos donde un VLM futuro sí sería necesario

- juegos con canvas (sin DOM/UIA) — leer HUDs, detectar fin de partida.
- PDFs escaneados / imágenes con texto compuesto (OCR puede no bastar).
- razonamiento espacial complejo ("el botón verde abajo a la derecha del logo").
- apps web con `<canvas>` puro o WebGL.
- detección semántica ("¿la página cargó completa?", "¿hay un error visual?").

Para todos estos casos, el contrato `ScreenObservation` ya está listo: un futuro `VLMProvider` solo necesita emitir `ScreenObservation(source="composite", ..., verifier_status=VerifierStatus.CONFIRMED, evidence=(...,))` y enchufarse al ladder en nivel 7. **Nada más** habrá que cambiar en el resto del agente.

---

## 14. Decisión final

**Veredicto:** `READY_TO_LAUNCH_TEXT_CORE_CLOSURE_FINAL`.

Justificación:
- el núcleo texto y el control de PC por texto siguen intactos y verdes (398/398);
- la base de percepción sin VLM quedó documentada, normalizada y blindada con tests;
- ningún hardcode por app/frase/modelo se introdujo;
- ningún LLM/VLM/cloud nuevo se agregó;
- chat trivial sigue sin tocar pantalla;
- GUI sin readback externo sigue cerrando como `UNVERIFIED`;
- contrato público `MissionStatus` y `TERMINATION_REASONS` está pinneado por test;
- todos los cambios son reversibles borrando 3 archivos y revirtiendo 25 líneas de `__init__.py`.

No hay bug bloqueante. No falta otra pasada de percepción dentro de la fase actual. Cualquier siguiente paso es **opcional** y vive en el backlog (§6).
