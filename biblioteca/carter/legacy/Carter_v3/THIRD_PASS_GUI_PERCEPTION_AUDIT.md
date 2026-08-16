# THIRD PASS GUI PERCEPTION AUDIT

## 1) Soporte real actual en Carter_v3 (GUI/screen/percepción)

Estado actual en `Carter_v3`:

- **Screenshot:**
  - tool `desktop_screenshot` en catálogo.
  - dispatch implementado en `dispatch_misc.py` (PowerShell en Windows).
  - verificación via `filesystem_write` (archivo existe/hash/size).
- **GUI click/type:**
  - tools `gui_click` y `gui_type` existen en catálogo.
  - dispatch actual es stub `not implemented in core` (no acción real).
  - verificador `gui_action` existe.
- **Window targeting / UIA:**
  - `window_list` (`dispatch_window.py`) expone títulos, ventana activa, proceso foreground y snapshot UIA (`UiaProbe`) cuando disponible.
  - `window_focus` existe y verifica foreground/UIA.
- **Perception router:**
  - `PerceptionRouter` define ladder (`INTERNAL -> ... -> SCREENSHOT/OCR/VLM`).
  - para chat/identidad/trivial usa `INTERNAL` (correcto para no contaminar).
- **OCR/VLM:**
  - no hay pipeline OCR/VLM real activo para núcleo texto (solo señalización de intención).
- **pywinauto/UI Automation:**
  - hay soporte parcial vía `UiaProbe` y verificación en `verifier.py`.
- **Screen/GUI gating:**
  - `select_tools()` solo prioriza screenshot/gui cuando `wants_vision` (nivel alto).
  - en conversación simple no debería entrar en ese camino.

Conclusión: Carter ya tiene base mínima técnica para screen/gui on-demand en modo conservador, pero necesita endurecer trazabilidad/permiso y honestidad de resultado GUI.

---

## 2) Qué tiene Mark en estas áreas

- `actions/screen_processor.py`: captura pantalla/cámara + sesión Gemini Live (audio/visión).
- `actions/computer_control.py`: pyautogui completo (click/type/hotkeys/screen_find con Gemini).
- `actions/desktop.py`: automatización desktop + generación/ejecución de código (Gemini).

Valor para Carter:
- ideas de segmentación de acciones GUI y utilidades de interacción.

Problemas para Carter (fase actual):
- acoplamiento cloud fuerte (Gemini).
- rutas de `Done` optimista.
- `generated_code` / `exec` prohibidos por filosofía Carter.
- mezcla de percepción activa con capas no necesarias para núcleo texto.

---

## 3) Ideas de Mark que sí sirven ahora

- estructura de acciones GUI separadas y explícitas (click/type/focus/screenshot).
- noción de “observación on-demand” antes de actuar.
- progresión interna: plan GUI -> actuar -> verificar.

---

## 4) Ideas de Mark que deben ir a backlog

- análisis visual inteligente/OCR/VLM completo.
- cualquier uso de cámara física.
- UX visual tipo Jarvis.
- screen_find basado en modelo externo.

---

## 5) Ideas de Mark prohibidas por `ContextoCarter.md`

- dependencia cloud obligatoria para percepción.
- `generated_code`/`exec` como mecanismo de acción.
- respuestas “Done” por defecto sin evidencia.
- automatización agresiva sin verificación robusta.

---

## 6) Dónde Carter puede usar percepción sin contaminar chat simple

Solo en rutas explícitamente accionables:

- petición explícita de screenshot/observación;
- acciones GUI que requieren contexto visual/ventana;
- follow-ups de misión compuesta donde ya hay contexto de acción.

Nunca en:
- saludo, identidad, charla general, inputs triviales, frustración conversacional.

---

## 7) Cómo evitar que trivial/chat dispare screenshot/visión

- mantener short-circuit de `trivial_lowinfo`/`ambiguous_short`.
- no subir `PerceptionLevel` en chat/identidad/knowledge.
- tests de no-regresión: trivial/identidad/chat no deben producir `desktop_screenshot`/`gui_*`.

---

## 8) Cómo debería verificarse una acción GUI

Regla mínima segura:

- si no hay readback externo confiable, resultado GUI debe ser `UNVERIFIED` (no `COMPLETED`).
- solo `COMPLETED` si hay evidencia verificable (foreground esperado, cambio observable, etc.).
- para riesgos altos por GUI, policy debe exigir aprobación (`NEEDS_PERMISSION` interno, `mission_status=needs_user` público).

---

## 9) Diferencia entre estados

- **NEEDS_USER:** falta dato/objetivo/aclaración.
- **NEEDS_PERMISSION:** falta autorización explícita para acción riesgosa.
- **NEEDS_ENVIRONMENT:** falta capacidad externa/dependencia/condición del sistema.
- **UNVERIFIED:** se intentó, pero no se pudo verificar causalmente.
- **FAILED:** ejecución/verificación falló de forma concluyente.
- **PARTIAL_WITH_NEXT_STEP:** avance parcial con pasos pendientes claros.

Nota de contrato público actual:
- `MissionStatus` sigue en 6 estados públicos.
- `NEEDS_PERMISSION` se expresa como estado interno/traza + `mission_status=needs_user` con `termination_reason` específico.

