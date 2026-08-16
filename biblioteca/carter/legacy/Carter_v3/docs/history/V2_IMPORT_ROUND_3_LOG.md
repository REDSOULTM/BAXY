# V2 -> V3 Import Round 3 - Live Log

> Trazabilidad incremental de la ronda. UIA determinista **interna**.
> Nunca expone `gui_do`, nunca infla la public tool surface.

Date: 2026-05-03
Author: Claude Opus 4.7
Source v2 modules consultados:
- `legacy/Carter_v2/src/carter_v2/capabilities/ui.py`
- `legacy/Carter_v2/src/carter_v2/adapters/uia.py`
- `legacy/Carter_v2/src/carter_v2/capabilities/window.py` (referencia)
- `legacy/Carter_v2/src/carter_v2/turn/verification.py` (referencia para `_verify_gui_action` y descartarla)

## Mision

Crear una capa UIA tier barata y determinista para:

- enumerar controles accesibles
- localizar controles por nombre/rol
- hacer focus/click/type minimo verificable
- resolver casos que hoy caerian demasiado pronto en screenshot/OCR

Sin `gui_do`. Sin hacks por app. UIA como capa **interna**.

## Plan ejecutado

1. Importar primitives UIA (NullAdapter + lazy pywinauto) a
   `src/carter_v3/perception/uia_probe.py`.
2. Integrar UIA al verifier (`_app_open`, `_window_action`) como
   evidencia **enriquecedora**, no determinante.
3. Integrar UIA al dispatcher (`window_list`) para que el LLM tenga
   el inventario UIA del foreground sin escalar a screenshot/OCR.
4. NO crear nuevos public tools. Cero impacto en la cap de 32 tools.
5. Tests + hardcode_guard + full matrix + cat13 matrix.

## Steps

### STEP 0 - log creado [DONE]

Archivo: `V2_IMPORT_ROUND_3_LOG.md`.

### STEP 1 - UiaProbe interno [DONE]

**Files added:**
- `src/carter_v3/perception/uia_probe.py` (NEW, 380 LOC)

**Que se porto:**
- patron NullAdapter / lazy `Desktop(backend="uia")` de
  `legacy/Carter_v2/src/carter_v2/adapters/uia.py`
- helpers `_safe_window_snapshot`, `_safe_control_snapshot`,
  `_collect_controls`, `_selector_kwargs` (formas equivalentes,
  pero deduplicadas y privadas a v3)
- contratos snapshot: `UiaWindowSnapshot`, `UiaControlSnapshot`,
  `UiaInspection` (dataclasses frozen, sin schemas externos)
- API minima: `is_available`, `list_windows`, `find_window`,
  `inspect_window`, `inspect_active_window`, `find_control`,
  `invoke_control`, `set_value_control`, `get_value_control`

**Que NO se porto y por que:**
- `WindowQuery` / `UiSelector` / `WindowRef` / `Capability` /
  `CapabilityRequest` / `CapabilityResult` / `Evidence` /
  `VerifiedFact` (clases del namespace `types.py` v2): v3 ya tiene
  `ToolCall` / `ToolResult` / `VerifiedOutcome` cerrados; replicarlos
  reabre superficie publica.
- `wait_for_window` con timeout abierto: v3 mantiene poll budget
  acotado (max 2s) en cada metodo para no romper L0.
- `inspect_active_window` con dependencia a `win32gui.GetForegroundWindow`
  del v2: v3 usa `ctypes.windll.user32.GetForegroundWindow` que ya
  esta en `WindowProbe` y no anade dependencia.
- `UiCapability.{find_element, invoke, set_value, get_value}` como
  capas separadas con `Evidence`/`VerifiedFact`: v3 expone los mismos
  verbos pero en una sola clase `UiaProbe` retornando snapshots
  inmutables, sin `Evidence` schema.
- TODA la wiring de v2 hacia adapters/tools: v3 NO crea tools
  publicos `ui_*`. La capa es estrictamente interna.

### STEP 2 - Integracion verifier [DONE]

**Files touched:**
- `src/carter_v3/tools/verifier.py`

**Que cambio:**
- nuevo helper `_uia_evidence_for_target(target)` que llama al
  `UiaProbe` compartido y devuelve `{ui_available, ui_root_available,
  ui_root_title, ui_root_class, ui_root_pid, ui_root_process}`.
- `_app_open`: tras encontrar process/window, enriquece la evidencia
  con UIA. **NO degrada** un CONFIRMED a PENDING si UIA no esta
  disponible — UIA es enriquecedor, no gate.
- `_window_action`: cuando no hay `active_title`, si UIA ve la raiz
  de la ventana objetivo entonces el resultado pasa de UNVERIFIABLE a
  PENDING con evidencia UIA real (cero fake success).

**Que NO se hizo:**
- NO se importo `_verify_gui_action` de v2 (`turn/verification.py`).
  Era weakly-verified ("ok=True → confirmed"), R3 lo descarta
  explicitamente. Las tools `gui_click`/`gui_type` siguen con
  verifier `gui_action` que no inventa exito.

### STEP 3 - Integracion dispatcher (`window_list`) [DONE]

**Files touched:**
- `src/carter_v3/tools/dispatch.py`

**Que cambio:**
- `_window_list` ahora retorna tres campos UIA nuevos:
  - `ui_available` (bool)
  - `ui_active_root` (bool)
  - `ui_active_controls` (list de {name, control_type, automation_id})
- BFS interno con `max_depth=2`, `max_controls=40`, dropea controles
  sin name/automation_id (ruido).
- Es el unico cambio sobre la public surface: 0 nuevos tools, mismo
  contrato de retorno (`window_list` ya retornaba `data` extensible).
- Permite que el LLM responda "que ventana esta activa" / "que
  elementos hay" / "verifica que X esta abierto" usando window_list
  sin forzar el ladder a subir a screenshot/OCR/VLM.

### STEP 4 - Optional dependency [DONE]

**Files touched:**
- `pyproject.toml` (nuevo extra `[ui]` = `["pywinauto>=0.6"]`)

`pywinauto` queda **optional**. La ausencia del paquete deja `UiaProbe`
en modo NullAdapter: la ladder cae limpiamente al siguiente nivel.

### STEP 5 - Tests [DONE]

**Files added:**
- `tests/test_uia_probe.py` (15 tests)

Cubren:
- `UiaProbe` no inicializa pywinauto en construccion.
- todos los metodos retornan la forma "unavailable" cuando el backend
  esta apagado (None / [] / False).
- `find_control` / `invoke_control` / `set_value_control` exigen al
  menos un campo de selector (no inventan target).
- `_app_open` integra evidencia UIA cuando esta disponible.
- `_app_open` NO degrada CONFIRMED a PENDING cuando UIA no esta.
- `_window_action` reporta PENDING + UIA evidence cuando no hay
  `active_title` pero UIA ve la raiz.
- `_window_action` reporta UNVERIFIABLE cuando ni active ni UIA.
- `window_list` siempre incluye las claves UIA (incluso si vacias).
- `window_list` filtra controles sin nombre.
- la public tool catalog **no** introduce ningun `ui_*` / `uia_*`
  / `gui_do`.

### STEP 6 - Validacion obligatoria [DONE]

- `python -m pytest -q`: **273 PASS**, 0 fail.
- `python audit/hardcode_guard.py`: **clean (44 files scanned)**.
- `python audit/full_matrix_runner.py --mode live-safe --label
  v2_import_round_3_full --out audit/runs/v2_import_round_3_full.json`:
  - global = **99.24%** (round 2 = 99.05% → +0.19 pp)
  - P1 = 100.0%, P2 = 98.55%, P3 = 100.0%
  - cat11 = 100.0%, cat18 = 100.0%
  - p95 = 1833.6ms
  - fails: C14.01, C14.02, C14.03, C14.04 (cat14 typos — fuera de
    scope round 3; round 2 tenia C14.01-04 + C14.09; C14.09 paso esta
    corrida).
- `python audit/full_matrix_runner.py --mode live-safe --category 13
  --label v2_import_round_3_cat13 --out
  audit/runs/v2_import_round_3_cat13.json`:
  - cat 13 cases ejecutados (live-safe-eligible) = 12/12 PASS = **100%**.
  - p95 = 423.3ms (round 2 = 401.8ms — variance dentro del margen).
  - prompts cubiertos: "que ventana esta activa", "which window is
    active", "que proceso esta en primer plano", "what's the foreground
    process", "lista las ventanas abiertas", "list open windows",
    "verifica que notepad esta abierto", "verify notepad is open",
    "verifica que la calculadora esta abierta", "verify calculator is
    open" + 2 padded.

## Entrega final

### 1. Que parte de `ui.py` si se porto

- patron NullAdapter + lazy backend (de `adapters/uia.py`).
- modelo de snapshot (window + element).
- BFS de hijos con `max_depth`.
- selectors `name / control_type / automation_id / class_name`.
- ladder de fallbacks invoke → click_input, set_edit_text → type_keys.

### 2. Que parte NO se porto y por que

- **`UiCapability`** como Capability publica: v3 NO expone una
  familia `ui_*`. El cap de 32 tools se preserva.
- **`Evidence` / `VerifiedFact` schemas**: v3 tiene `VerifiedOutcome`
  y `ToolResult.data`; otra capa de schema duplicaria contratos.
- **`WindowQuery` / `WindowRef` types**: replicarlos abriria una
  superficie de tipos paralela; UIA snapshots viven en
  `perception/uia_probe.py` y nadie mas los necesita.
- **`wait_for_window` con timeout libre**: v3 acota poll a 2s para
  no romper L0 / L1 latency budgets.
- **`gui_do` / `_verify_gui_action`** (de `turn/verification.py`):
  rechazados por contrato. Round 3 NO normaliza el patron de "ok=True
  → confirmed".

### 3. Como quedo la ladder barata

Antes de round 3 (`process > window > system_api > web > screenshot
> OCR > VLM`), nivel 2 (WINDOW_UIA) dependia solo de `WindowProbe`
(EnumWindows + GetForegroundWindow). Despues de round 3:

- nivel 2 ahora consulta tambien `UiaProbe` cuando esta disponible:
  - en `window_list` -> el caller obtiene `ui_active_controls` inline.
  - en verifier de `app_open` -> evidence UIA inline.
  - en verifier de `window_focus` -> evidence UIA cuando no hay
    `active_title`.
- nivel 5/6/7 (screenshot / OCR / VLM) sigue siendo last resort,
  ahora con un step intermedio mas resolutivo.

### 4. Que subio realmente en C13

- C13 live-safe-eligible: 12/12 = **100%** (mismo numero absoluto
  que round 2; cat 13 ya estaba al 100% para los prompts marcados
  live-safe).
- Lo que mejoro y NO mide la matriz live-safe:
  - el `data` de `window_list` ahora trae `ui_active_controls` real
    en hosts con pywinauto, lo que da material verificable para
    prompts del tipo "que elementos UIA hay" / "encuentra el boton
    Aceptar" (C13.31, C13.33), que en `mode=live` (no live-safe)
    pasarian sin tener que tocar `vision_*`.
  - el verifier `_app_open` ahora deja en `evidence` un
    `ui_root_available=True/False`. Eso no cambia el `mission_status`
    estructural, pero da al composer/LLM senal extra para responder
    "verifica que X esta abierto" sin escalar a screenshot.
- Conclusion honesta: la mejora visible en numeros es minima porque
  la matriz live-safe ya estaba tope. La mejora real es estructural,
  visible en `mode=live` (no auditado en esta corrida por seguridad)
  y en hosts con pywinauto instalado.

### 5. Resultados reales

| validacion                         | antes round 3            | despues round 3          |
|------------------------------------|--------------------------|--------------------------|
| pytest                             | 258 pass / 0 fail        | 273 pass / 0 fail        |
| hardcode_guard                     | clean (43 files)         | clean (44 files)         |
| full live-safe global              | 99.05% (5 fails)         | 99.24% (4 fails)         |
| full live-safe p95                 | 1785.8ms                 | 1833.6ms                 |
| cat 13 live-safe                   | 100% (p95 401.8ms)       | 100% (p95 423.3ms)       |
| public tools                       | 32                       | 32                       |
| `gui_do` exposed                   | NO                       | NO                       |
| brand strings hardcoded            | 0                        | 0                        |

### 6. Riesgos

- **R-V3-9 (NEW): pywinauto cold-start**. Primera llamada a
  `_get_uia_probe().is_available()` o `find_window()` sobre un host
  con pywinauto fresco puede tardar ~150-400ms inicializando
  comtypes / Desktop. Mitigado: `_get_uia_probe` cachea la instancia
  a nivel modulo; `_init_attempted` evita reintentos. Si el preload
  del agent quiere resolverlo proactivamente puede llamar
  `verifier._get_uia_probe().is_available()` al startup.
- **R-V3-10 (NEW): variance UIA en hosts con DPI scaling
  agresivo / sesiones RDP**. `pywinauto` puede devolver
  `is_visible()=False` para ventanas que el usuario sigue viendo.
  Tratado como "no UIA root reachable" → el verifier reporta PENDING
  honesto con `ui_root_available=False`, nunca CONFIRMED inventado.
- **C14.01-04 sigue rojo**: typo handling no es scope round 3.
  Permanece en R-V3-X / R-V2-B7 hasta round 4.

### 7. Updates docs

- `Carter_v3/CHANGELOG.md` -> entrada **Round 3**.
- `Carter_v3/RESIDUAL.md` -> entradas **R-V3-9, R-V3-10**.
- `Carter_v3/V2_IMPORT_ROUND_3_LOG.md` (este archivo).

## Descartes explicitos (round 3)

- `gui_do` como tool publico (mantiene escenario v2 weak-verified).
- `UiCapability` con namespace publico `ui.*`.
- `Evidence` / `VerifiedFact` schemas duplicados.
- Tipos paralelos `WindowQuery` / `WindowRef`.
- Aliases por app o por marca.
- Cualquier listado de "apps con UIA buena vs mala" — la calidad UIA
  se reporta en evidencia, nunca como switch.
