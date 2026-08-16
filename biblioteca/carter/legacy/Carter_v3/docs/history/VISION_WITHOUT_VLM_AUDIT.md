# VISION_WITHOUT_VLM_AUDIT

Pasada: **VISION_WITHOUT_VLM_FOUNDATION**
Fase: 1 — Auditoría
Modo: Opus 4.7 Medium / análisis sin tocar código.

Objetivo: documentar exactamente qué puede percibir Carter HOY sin VLM,
sin LLM extra, sin Gemini, sin cloud y sin visión pesada, y dónde
están los huecos reales para cerrar la base local de percepción.

> Documentos leídos: [ContextoCarter.md](../ContextoCarter.md) (workspace root),
> [THIRD_PASS_GUI_PERCEPTION_AUDIT.md](THIRD_PASS_GUI_PERCEPTION_AUDIT.md),
> [THIRD_PASS_GUI_PERCEPTION_PLAN.md](THIRD_PASS_GUI_PERCEPTION_PLAN.md),
> [THIRD_PASS_GUI_PERCEPTION_REPORT.md](THIRD_PASS_GUI_PERCEPTION_REPORT.md),
> [THIRD_PASS_MISSION_STATUS_TRACE_REPORT.md](THIRD_PASS_MISSION_STATUS_TRACE_REPORT.md),
> [SECOND_PASS_TEXT_CORE_HARDENING_REPORT.md](SECOND_PASS_TEXT_CORE_HARDENING_REPORT.md),
> [MARK_TO_CARTER_TEXT_CORE_REPORT.md](MARK_TO_CARTER_TEXT_CORE_REPORT.md).
>
> Todos existen y son consistentes con la pasada anterior.

---

## 1. ¿Qué puede "ver" Carter hoy sin VLM?

### 1.1 Procesos / ventanas / foco
- [perception/probe.py](src/carter_v3/perception/probe.py) expone:
  - `ProcessProbe.names()` — vía `psutil`, lowercased, sin `.exe`, TTL 2s.
  - `ProcessProbe.is_running(target)`.
  - `WindowProbe.windows()` y `WindowProbe.titles()` — `EnumWindows` Win32 + `psutil` para `process_name` por hwnd, TTL 2s, fallback `[]` en no-Windows.
  - `SystemInventory` agrega ambas con caché.
- Tools públicas dispatch:
  - `process_list` → [tools/dispatch.py](src/carter_v3/tools/dispatch.py#L67)
  - `window_list` → expuesto en `WindowDispatchMixin`; entrega títulos, ventana activa y proceso foreground.
  - `window_focus` → real, con verificación de foreground/UIA.

### 1.2 Foreground / ventana activa
- `WindowProbe` detecta visibilidad y `process_name` por hwnd.
- `window_list` devuelve activa + foreground.
- `UiaProbe.inspect_active_window()` resuelve la foreground vía `GetForegroundWindow`.

### 1.3 UIA / accessibility tree
- [perception/uia_probe.py](src/carter_v3/perception/uia_probe.py):
  - lazy `pywinauto Desktop(backend="uia")`, NullAdapter si no disponible.
  - `is_available()`, `list_windows()`, `find_window()`, `inspect_window()`,
    `inspect_active_window()`, `find_control()`.
  - snapshots:
    - `UiaWindowSnapshot`: title, process_name, pid, class_name, automation_id, is_visible.
    - `UiaControlSnapshot`: name, control_type, automation_id, class_name, value, is_enabled, is_offscreen, **bounding_rect (tuple int x4)**.
    - `UiaInspection`: window + lista de controles (BFS, max_depth=2, cap=200).
  - todo internal — Carter v3 NO expone `gui_do`/`ui_*` en el surface público.
- Limitaciones reales:
  - depende de `pywinauto`; si no está, todo retorna seguro vacío (sin `raise`).
  - no tiene fallback a MSAA — solo backend UIA.
  - apps Electron/CEF reportan árboles muy planos o vacíos: queda como riesgo conocido.
  - no hay readback semántico tipo "este botón ahora dice 'OK'" más allá de `value`.

### 1.4 Screenshot
- Tool: `desktop_screenshot` con `path`.
- Dispatch: [tools/dispatch_misc.py](src/carter_v3/tools/dispatch_misc.py#L37) — PowerShell + `System.Drawing` (Windows-only). En no-Windows devuelve `ok=False message="screenshot_supported_on_windows_only"`.
- Verificación:
  - `path.parent.mkdir`,
  - `proc.returncode == 0`,
  - `path.exists() and path.stat().st_size > 0`,
  - retorna `data={"path", "size"}`.
- El verificador genérico de filesystem complementa con existencia/tamaño/hash cuando aplica.
- Estado terminal honesto: si la captura falla, `ok=False` con mensaje real (no fake success).

### 1.5 PerceptionRouter
- [perception/ladder.py](src/carter_v3/perception/ladder.py): niveles 0..7 (`INTERNAL`, `PROCESS`, `WINDOW_UIA`, `SYSTEM_API`, `WEB_AUTOMATION`, `SCREENSHOT`, `OCR`, `VLM`).
- `PerceptionRouter.decide(kind, explicit_visual_request)`:
  - chat / identity / knowledge / trivial / memory / style → `INTERNAL`.
  - screenshot/ocr/vlm requeridos → solo cuando `explicit_visual_request=True` o `kind` lo pide explícitamente.
  - default → `PROCESS` (más barato).

### 1.6 GUI act/verify
- `gui_click`, `gui_type` están registrados en el catálogo y en el dispatcher como **stubs** (`ok=False message="not implemented in core"`).
- `RiskLevel.HIGH` en ambos: la `PolicyEngine` exige aprobación → emite `policy_block_high_risk_no_approval` y termina `NEEDS_USER` (interno `NEEDS_PERMISSION`).
- El verifier `gui_action` ya no confirma por defecto: sin readback externo → `UNVERIFIABLE`.

### 1.7 Estados y termination_reason
- Estados internos canónicos (no públicos): `OBSERVING_SCREEN`, `GUI_PLANNING`, `GUI_ACTING`, `VERIFYING_SCREEN`, `NEEDS_PERMISSION`, `UNVERIFIED`, `PARTIAL_WITH_NEXT_STEP`.
- Aparecen solo en rutas screen/gui reales (probado en
  [test_agent_integration.py](tests/test_agent_integration.py#L1546)).
- Públicos (`MissionStatus`): `trivial`, `complete`, `partial`, `failed`, `needs_user`, `unverified` — frozenset, contrato no roto.
- `termination_reason` incluye `needs_permission`, `needs_environment`, `policy_block_high_risk_no_approval`, `verifier_status_unverifiable`, etc. (frozenset cerrado).

---

## 2. ¿Qué tan útil es UiaProbe hoy?

| Capacidad | Estado |
|---|---|
| Títulos de ventanas | ✔ `list_windows` |
| Process / window info (pid, class, automation_id, visibilidad) | ✔ |
| Elementos UI por ventana | ✔ `inspect_window` con cap 200 |
| Nombres de controles | ✔ `name`, `control_type`, `automation_id` |
| Bounding boxes | ✔ `bounding_rect` |
| Targetear botones / campos | ✔ `find_control` por nombre/tipo/automation_id/class |
| Lectura de `value` (textboxes, etc.) | ✔ campo `value` en snapshot |
| Fallback honesto sin pywinauto | ✔ retorna `[]` / `None` / `False` |
| Apps Electron / CEF | ✘ árbol pobre — limitación conocida |
| Backend MSAA fallback | ✘ no implementado |
| Readback semántico “después de X, ahora aparece Y” | ⚠ parcial (sólo si caller compara dos snapshots) |
| Modelo de datos común con screenshot/OCR | ✘ cada capa devuelve su forma propia |

**Veredicto:** UIA cubre la mayoría de "ver y targetear" en apps Win32/WPF/UWP. Lo limita Electron/CEF y la falta de un objeto observación común.

---

## 3. ¿Qué tiene Carter hoy para screenshot?

- **Tool:** `desktop_screenshot(path)`.
- **Dispatch:** PowerShell con `System.Drawing.Bitmap.CopyFromScreen`. Sin dependencia Python extra.
- **Verifier:** comprueba `returncode==0`, `path.exists()`, `path.stat().st_size > 0`.
- **Evidencia:** `data={"path", "size"}`. NO se computa hash (no es necesario hoy).
- **No-Windows:** `ok=False message="screenshot_supported_on_windows_only"` — sin fake success.
- **Estados terminales esperados:**
  - éxito → `complete` con `verifier_status_confirmed` por filesystem.
  - falla → `failed` con `all_tools_failed` o `unverified` si ok pero sin evidencia (no debería pasar — el dispatch ya garantiza ambas condiciones).

---

## 4. ¿Qué tiene Carter hoy para GUI?

- `gui_click` y `gui_type` existen como **stubs reales** (`ok=False`), con `RiskLevel.HIGH`.
- Policy: requieren aprobación → sin ella `NEEDS_USER` + `policy_block_high_risk_no_approval`.
- Verifier: sin readback externo, `UNVERIFIABLE`. Aprobado pero sin readback → `UNVERIFIED`. Esto está cubierto por
  [test_gui_action_without_external_readback_ends_unverified_with_approval](tests/test_agent_integration.py#L1493).
- No pueden terminar en fake success.
- No están bloqueados — están permitidos previo gating de policy.

---

## 5. ¿Qué falta para una percepción robusta sin VLM?

| Item | Clasificación | Notas |
|---|---|---|
| `ScreenObservation` / `PerceptionObservation` (contrato común) | **Necesario ahora** | Hoy cada capa devuelve su shape. Un objeto liviano normaliza UIA + screenshot + OCR-futuro y permite verifier consistente. |
| `OCRProvider` + `OCRUnavailableProvider` (skeleton) | **Necesario ahora** (skeleton, sin instalar nada) | Define contrato y permite que verifier responda `UNVERIFIED` / `needs_environment` honestamente cuando alguien lo pida. |
| Tests anti-regresión gating de percepción | **Necesario ahora** | Bloquear que evolución del router/select_tools rompa “no screenshot para hola”. |
| `EvidenceFragment` con `source/confidence` | Útil pero backlog | Se puede agregar más adelante; por ahora `verifier_outcomes[].evidence` cumple. |
| `image_diff` básico (PIL/imghash) | Backlog | Aporta evidencia débil; requiere PIL instalado → mejor diferir. |
| `template_match` | Backlog | Igual: dependencia (OpenCV) pesada para el aporte. |
| MSAA fallback en UIA | Backlog | Solo si Electron/CEF se vuelve un blocker real. |
| OCR real (Tesseract / Paddle) | Backlog | Requiere binario; solo cuando un caso real lo pida. |
| VLM local | **No recomendable ahora** | Fuera de fase. Requiere modelo + VRAM + latencia. Ver §13 del REPORT. |
| Visión always-on | **Peligroso** | Rompe privacidad y velocidad. Prohibido por `ContextoCarter.md`. |
| Stream de pantalla (cloud/Gemini Live) | **Peligroso** | Rompe local-first. Prohibido. |

---

## 6. Jerarquía correcta de percepción (ladder recomendada)

Mapea exactamente al `PerceptionLevel` actual; este audit lo ratifica.

| Nivel | Capa | Cuándo usar |
|---|---|---|
| 0 | INTERNAL / contexto | chat, identidad, conocimiento, memoria, trivial, follow-up textual. |
| 1 | PROCESS (`psutil`) | "¿está abierto X?", verificar app antes de actuar. |
| 2 | WINDOW + UIA | "¿qué ventana está activa?", localizar control para clickear, leer valor de un textbox. |
| 3 | SYSTEM_API | volumen, batería, hora, red — no necesita pantalla. |
| 4 | WEB_AUTOMATION | solo cuando sea Carter quien navega; no es percepción de pantalla del usuario. |
| 5 | SCREENSHOT | "captura la pantalla" o como evidencia post-acción cuando UIA no alcanza. |
| 6 | OCR (opcional / skeleton) | extraer texto cuando UIA no expuso `value` y se pidió leer pantalla. |
| 7 | VLM | NO usar en esta fase. Reservado a futuro para razonamiento visual de alta dificultad. |

Regla: subir un nivel solo si el anterior no resolvió. Nunca saltar al 5/6/7 en chat o identidad.

---

## 7. Gating correcto

Carter NO debe activar percepción cuando:

- input trivial (`a`, `ok`, `nada`, `qué?`).
- saludo / identidad (`hola`, `quién eres`, `gracias`).
- conocimiento general / chat / estilo / memoria sin acción.
- frustración / insulto / venting.
- preguntas hipotéticas o conversacionales sin objetivo de pantalla.

Carter SÍ debe activar percepción cuando:

- petición explícita visual (`qué ves`, `screenshot`, `lee la pantalla`).
- acción GUI explícita (`click ahí`, `escribe esto en X`).
- misión compuesta GUI (`abre X y haz click en Y`).
- follow-up directo de una misión GUI activa (continuidad de sesión).

Implementación actual: `select_tools()` en
[turn_support.py](src/carter_v3/turn_support.py#L51) sólo prioriza
screenshot/gui cuando `wants_vision = perception_level >= SCREENSHOT`,
y filtra cualquier `gui_*`/`desktop_screenshot` del catálogo si no.
La decisión de nivel viene de `PerceptionRouter` que en chat/identidad
devuelve `INTERNAL`. **Test ya cubre 5 prompts triviales**
([test_simple_chat_inputs_never_activate_screen_or_gui](tests/test_agent_integration.py#L1439)).

Gap: faltan tests de no-regresión específicos para frustración,
conocimiento general, memoria pasiva y follow-up no-GUI.

---

## 8. Estados y resultados honestos esperados

| Caso | mission_status público | termination_reason | Estado interno terminal |
|---|---|---|---|
| screenshot exitoso + verificado | `complete` | `all_tools_confirmed` | `COMPLETE` |
| screenshot falla (ok=False) | `failed` | `all_tools_failed` | `FAILED` |
| screenshot ok pero archivo vacío | `failed` | `all_tools_failed` | `FAILED` (dispatch ya lo marca `ok=False`) |
| UIA no disponible (sin pywinauto) | `unverified` o `needs_user`+`needs_environment` | `verifier_status_unverifiable` o `needs_environment` | `UNVERIFIED` / `NEEDS_ENVIRONMENT` |
| UIA devuelve vacío | `unverified` | `verification_inconclusive` | `UNVERIFIED` |
| OCR no instalado y se pidió | `needs_user` | `needs_environment` | `NEEDS_ENVIRONMENT` |
| OCR sin texto | `unverified` | `verification_inconclusive` | `UNVERIFIED` |
| `gui_click` ejecutado, sin readback | `unverified` | `verifier_status_unverifiable` | `UNVERIFIED` |
| `gui_type` ejecutado, sin readback | `unverified` | `verifier_status_unverifiable` | `UNVERIFIED` |
| Imagen cambió, sin evidencia semántica | `unverified` | `verification_inconclusive` | `UNVERIFIED` |
| Acción parcial (paso 1 ok, paso 2 sin readback) | `partial` | `partial_some_tools_unverified` | `PARTIAL_WITH_NEXT_STEP` |
| Acción bloqueada por permiso | `needs_user` | `policy_block_high_risk_no_approval` o `needs_permission` | `NEEDS_PERMISSION` |
| Acción ambigua | `needs_user` | `ambiguity_target_unresolved` | `NEEDS_USER` |

Notas:
- `NEEDS_PERMISSION` y `NEEDS_ENVIRONMENT` son **estados internos / termination_reason**; el contrato público sigue en 6 valores (no romper).
- Ya están registrados en `TERMINATION_REASONS` (frozenset cerrado en
  [contracts.py](src/carter_v3/contracts.py#L48)).

---

## Resumen del estado actual

Carter ya tiene una base sorprendentemente sólida sin VLM:
- ladder completo,
- probes de proceso/ventana con TTL,
- UIA real con fallback honesto,
- screenshot con evidencia mínima,
- gating de gui/screen funcionando para chat trivial,
- estados internos GUI/percepción ya canónicos,
- contrato público intacto.

Los huecos reales son:
1. **No hay un contrato común de observación** que normalice UIA/screenshot/OCR — cada capa habla su propio idioma.
2. **No hay skeleton OCR** — cuando alguien implemente OCR real, no hay un contrato al que conectar; tampoco hay forma honesta de decir "OCR no disponible".
3. **Gating tests son mínimos** — un cambio futuro en `select_tools()` o el ladder podría reactivar GUI sin que ningún test grite.

El plan en [VISION_WITHOUT_VLM_PLAN.md](VISION_WITHOUT_VLM_PLAN.md) propone exactamente 3 cambios mínimos para cerrar esos huecos sin romper nada y sin meter VLM.
