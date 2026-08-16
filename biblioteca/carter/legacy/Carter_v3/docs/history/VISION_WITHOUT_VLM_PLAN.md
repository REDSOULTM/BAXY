# VISION_WITHOUT_VLM_PLAN

Pasada: **VISION_WITHOUT_VLM_FOUNDATION**
Fase: 2 — Plan mínimo (máximo 3 cambios).

> Basado en [VISION_WITHOUT_VLM_AUDIT.md](VISION_WITHOUT_VLM_AUDIT.md).
> Cada cambio es pequeño, reversible, sin dependencias nuevas, sin
> tocar contratos públicos. **Ningún cambio agrega VLM, OCR real,
> cloud, voz, cámara o LLM extra.**

---

## CAMBIO A — Contrato `ScreenObservation` (perception/observation.py)

### Problema
Hoy UIA, screenshot y (futuro) OCR devuelven shapes distintas (`UiaInspection`, `ToolResult.data["path","size"]`, etc.). Un verifier o un caller que quiera combinar dos capas ("UIA dice 'OK', screenshot existe → confianza alta") tiene que hablar varios idiomas. No hay un objeto evidencia común.

### Por qué importa
- Es la base para que Carter pueda razonar honestamente sobre lo que percibió.
- Sin él, agregar OCR/image-diff más adelante exigirá refactor.
- Sin él, los tests de evidencia siguen siendo ad-hoc por capa.

### Archivos a tocar
- **NUEVO**: [src/carter_v3/perception/observation.py](src/carter_v3/perception/observation.py)
- **EDITAR**: [src/carter_v3/perception/__init__.py](src/carter_v3/perception/__init__.py) — exportar nombres.

### Implementación mínima
- `EvidenceFragment` (dataclass frozen): `source: str`, `kind: str`, `payload: dict`, `confidence: float = 0.0`.
- `UIElementObservation` (dataclass frozen): `name`, `control_type`, `automation_id`, `value`, `bounds: tuple[int,int,int,int]|None`.
- `ScreenObservation` (dataclass frozen): `source: str` (`"uia"|"screenshot"|"ocr"|"composite"`), `window_title: str = ""`, `process_name: str = ""`, `bounds: tuple|None = None`, `ui_elements: tuple[UIElementObservation,...] = ()`, `text: str = ""`, `screenshot_path: str = ""`, `evidence: tuple[EvidenceFragment,...] = ()`, `confidence: float = 0.0`, `errors: tuple[str,...] = ()`, `needs_environment: bool = False`, `verifier_status: str = "pending"` (validado contra `VERIFIER_STATUSES`).
- Helper `from_uia_inspection(insp)` para convertir un `UiaInspection` (capa 2 del ladder) a `ScreenObservation`. **No** convierte automáticamente — solo está disponible si el caller lo pide.
- **NO** se enchufa todavía a verifier/dispatch — es solo contrato disponible. Cero impacto en runtime.

### Riesgo
Mínimo: archivo nuevo, no se importa desde paths críticos. El export en `__init__.py` agrega símbolos pero no rompe ninguno previo.

### Rollback
Borrar `observation.py` y revertir las 4 líneas en `__init__.py`.

### Tests
- `test_screen_observation_validates_verifier_status`
- `test_screen_observation_from_uia_inspection_roundtrip` (usa `UiaInspection` artificial — no requiere pywinauto).
- `test_evidence_fragment_immutable` (frozen).

### Criterio de éxito
- importable;
- no aparece en `tool_calls`/`AgentTurnResult`;
- no se usa en runtime hoy → ningún test existente cambia.

### Alineación con `ContextoCarter.md`
- local-first, sin LLM extra, sin cloud, sin voz, sin VLM.
- honestidad: `verifier_status` obligatorio + `errors` + `needs_environment` evita fake success.
- privacidad: solo describe lo que ya estaba en pantalla; ningún canal nuevo.

---

## CAMBIO B — Skeleton `OCRProvider` + `OCRUnavailableProvider`

### Problema
No hay contrato OCR. Si alguien implementa OCR real más tarde (Tesseract, Paddle), terminará usando un shape ad-hoc, y mientras tanto no hay forma estructurada de responder honestamente "OCR no está disponible en este host".

### Por qué importa
- Permite que un caller pida `provider.read_text(path)` y siempre reciba un `OCRResult` con `available: bool` + `needs_environment: bool`.
- Hace explícito el contrato sin obligar a instalar nada.
- Bloquea fake success por accidente: el provider unavailable nunca devuelve texto.

### Archivos a tocar
- **NUEVO**: [src/carter_v3/perception/ocr.py](src/carter_v3/perception/ocr.py)
- **EDITAR**: [src/carter_v3/perception/__init__.py](src/carter_v3/perception/__init__.py) — exportar nombres.

### Implementación mínima
- `OCRResult` (dataclass frozen): `available: bool`, `text: str = ""`, `confidence: float = 0.0`, `engine: str = ""`, `error: str = ""`, `needs_environment: bool = False`.
- `OCRProvider` (Protocol): `name: str`, `is_available() -> bool`, `read_text(path: str) -> OCRResult`.
- `OCRUnavailableProvider`: implementación por defecto. `is_available() -> False`. `read_text` devuelve `OCRResult(available=False, needs_environment=True, error="ocr_not_installed", engine="unavailable")`.
- **NO** se importa Tesseract/Paddle. **NO** se registra como tool pública. Solo contrato + default unavailable.

### Riesgo
Mínimo: nuevo archivo, sin imports externos, no enchufado a runtime.

### Rollback
Borrar `ocr.py` y revertir export en `__init__.py`.

### Tests
- `test_ocr_unavailable_provider_marks_needs_environment`
- `test_ocr_unavailable_provider_never_returns_text`
- `test_ocr_result_immutable` (frozen).

### Criterio de éxito
- importable;
- `OCRUnavailableProvider().read_text("anything")` jamás devuelve `available=True`;
- ningún test existente cambia.

### Alineación con `ContextoCarter.md`
- no instala dependencias;
- no agrega cloud;
- responde honestamente "no disponible" sin inventar texto.

---

## CAMBIO C — Tests anti-regresión de gating de percepción

### Problema
Hoy hay 1 test (`test_simple_chat_inputs_never_activate_screen_or_gui`) con 5 prompts. Cualquier cambio futuro en `select_tools()` o `PerceptionRouter` que reactive accidentalmente `desktop_screenshot`/`gui_*` para frustración / conocimiento / memoria pasiva pasaría sin alarma.

### Por qué importa
- Es la guard rail que evita que percepción se cuele en chat normal.
- Cubre los nuevos contratos (CAMBIO A/B) demostrando que **no rompen** el comportamiento existente.

### Archivos a tocar
- **NUEVO**: [tests/test_vision_without_vlm.py](tests/test_vision_without_vlm.py)

### Implementación mínima
Un único archivo con tests cortos:
1. `PerceptionRouter` no escala a SCREENSHOT/OCR/VLM para frustración / memoria / knowledge / chat / identity / trivial / style — sin `explicit_visual_request`.
2. `PerceptionRouter` con `explicit_visual_request=True` sí entra en la ruta visual (regresión de la ruta legítima).
3. `select_tools(perception_level=INTERNAL)` no incluye `desktop_screenshot` ni ningún `gui_*`.
4. `select_tools(perception_level=SCREENSHOT)` sí incluye `desktop_screenshot`.
5. Contrato `ScreenObservation` rechaza `verifier_status` inválido (defensa estructural).
6. `OCRUnavailableProvider` jamás reporta éxito.
7. `MissionStatus` y `TERMINATION_REASONS` siguen siendo el frozenset esperado (regresión de contrato público — protege la pasada anterior).
8. `PerceptionLevel.VLM` no se elige en ninguna decisión que no sea `screen_visual` o `vision_required_full` explícito (asegura que la fase actual no usa VLM "por accidente").

### Riesgo
Cero — solo añade tests.

### Rollback
Borrar el archivo.

### Criterio de éxito
- los 8 nuevos tests pasan;
- los tests existentes siguen pasando.

### Alineación con `ContextoCarter.md`
- protege privacidad (no screenshot en chat),
- protege velocidad (no UIA en saludo),
- protege honestidad (no completar sin evidencia),
- protege contrato público.

---

## Cambios NO incluidos (y por qué)

| Idea | Decisión | Motivo |
|---|---|---|
| `image_diff` básico (CAMBIO D del prompt) | Backlog | Aporta evidencia *débil* y agrega presión por instalar PIL. No vale el costo en esta fase. |
| OCR real (Tesseract/Paddle) | Backlog | Requiere binario externo. Skeleton ya cubre el contrato hasta que aparezca un caso real. |
| MSAA fallback en UIA | Backlog | Solo si Electron/CEF se vuelve un blocker explícito. |
| Convertir `UiaInspection` automáticamente a `ScreenObservation` en runtime | Backlog | Cambia comportamiento — viola "máximo 3 cambios" y añade riesgo. Mejor dejar el helper opt-in. |
| Tools públicas nuevas (`screen_observe`, `ocr_read`) | Rechazado | Aumentaría surface y romperia contrato. |
| Cambiar `MissionStatus` para exponer `NEEDS_PERMISSION`/`NEEDS_ENVIRONMENT` | Rechazado | Romperia contrato público fijado en PARTE 1. Ya se cubre como `termination_reason`. |

---

## Resumen

3 cambios. Todos archivos nuevos o ediciones de 1-line export.
- **A**: contrato `ScreenObservation` + `UIElementObservation` + `EvidenceFragment`.
- **B**: contrato `OCRProvider` + `OCRResult` + `OCRUnavailableProvider`.
- **C**: tests no-regresión de gating + protección de contrato público.

Resultado esperado: Carter queda **listo** para que cualquier mejora futura de percepción (OCR real, image-diff, MSAA, etc.) se enchufe contra contratos honestos y normalizados, sin que la pasada actual cambie ni un comportamiento observable.
