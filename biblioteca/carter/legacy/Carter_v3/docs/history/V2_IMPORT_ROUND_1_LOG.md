# V2 → V3 Import — Round 1 — Live Log

> Trazabilidad incremental de la ronda. Cada step se marca cuando termina,
> con archivos tocados y resultado de validación. Si el agente que escribe
> esto se corta, otro agente puede retomar leyendo el último step `[DONE]`.

Date: 2026-05-03
Author: Claude (continuado desde audit GPT 5.5)

## Plan acordado (3 piezas alto-ROI / bajo-riesgo)

1. **AUDIO REAL** (`media.py` → `dispatch._system_set_volume` + `_system_mute`)
   - Hoy son lambdas echo: devuelven `{"level": N}` sin escribir nada en pycaw.
   - Verifier ya lee con pycaw, así que escritura real cierra el gap.
   - Cambia material `verifier_status` de `pending`/`failed` a `confirmed`.

2. **APP RESOLVER** (`app_resolver.py` → nuevo `perception/app_resolver.py`)
   - `Get-StartApps | ConvertTo-Json` con TTL 300s.
   - `_norm` Unicode-correct (Latin diacritic strip + NFC restore para CJK).
   - Sin hardcodes (`_ALIASES = {}` mantenido vacío).

3. **APPSFOLDER LAUNCH** (`process.py` → `dispatch._app_open` ladder)
   - Si `AppResolver.resolve_launch(target)` devuelve `shell:appsfolder\\<AppID>`,
     usar `subprocess.Popen(["explorer.exe", launch_name])`.
   - Cubre Microsoft Store apps (Settings, Calculator nuevo, Spotify-store, Edge moderno).

## Lo que NO se importa esta ronda (descartes documentados)

- `process._stop_app` graceful_close (necesita `_graceful_close.py` + WM_CLOSE COM, demasiado).
- `process._uninstall_app` winget+registry (alto riesgo, expone superficie).
- `window.py` rich actions (focus/wait/minimize/maximize): no resuelve gap activo.
- `ui.py` UIA: ronda dedicada futura.
- `filesystem.py` zip/unzip/copy/move: sin gap activo.
- `terminal.py` allowlist: la policy ya cubre lo crítico.
- `gui_agent.py`, `steam_*`, `office_*`, `web_profile_*`, `web_extension_relay_*`,
  `web_connect_cdp`, `meta_*`: descarte permanente per audit.

## Invariantes a no romper

- `mission_status` ∈ {trivial, complete, partial, failed, needs_user, unverified}
- `VerifiedOutcome.status` ∈ {confirmed, pending, failed, skipped, unverifiable}
- catálogo público sigue ≤ 32 tools (no añadimos tools, mejoramos handlers)
- `compute_mission_status` sigue estructural
- cero fake success
- cero hardcodes de marca
- agent.py se mantiene en margen sano
- aislamiento `Carter_v3/` estricto

## Baseline antes de empezar

- pytest: 200 passed
- hardcode_guard: clean (41 archivos)
- agent.py: 447 líneas
- total `src/carter_v3`: 4802 líneas
- catálogo: 32 tools

---

## Steps

### STEP 0 — log creado [DONE]

Archivo: `V2_IMPORT_ROUND_1_LOG.md`.

### STEP 1 — Audio real en dispatch [DONE]

**Files touched:**
- `src/carter_v3/tools/dispatch.py`:
  - 2 lambdas reemplazadas por `_system_set_volume` y `_system_mute` (handlers reales).
  - Net: +47 líneas (~340 → 387).
- `src/carter_v3/tools/verifier.py`:
  - Extraída helper `_get_endpoint_volume_interface()` (DRY entre read/write).
  - `_read_volume_level` y `_read_mute_state` reducidas a 4 líneas cada una.
  - Net: -22 líneas.

**Behavioural change:**
- Antes: `system_set_volume {level: 30}` devolvía `ToolResult(ok=True, data={"level": 30})` sin escribir nada. Verifier leía `actual` con pycaw, generalmente devolvía `pending` por mismatch.
- Ahora: pycaw `SetMasterVolumeLevelScalar(0.30, None)` → readback inmediato → `data={"level": actual, "requested": 30}`. Verifier confirma con tolerancia ±5.
- Mismo patrón para `system_mute`.

**Validation:**
- pytest -q: 200 passed (igual que baseline)
- Smoke: `ToolDispatcher()` carga sin error, ambos handlers registrados.
- Sin pycaw instalado: handler devuelve `ok=False, message="volume_unavailable: ..."` con next_step_hint.

**Risk:** zero — el sin-pycaw fallback está limpio.

### STEP 2 — Nuevo app_resolver [DONE]

**Files touched:**
- `src/carter_v3/perception/app_resolver.py` (NEW): 175 líneas.
- `src/carter_v3/perception/__init__.py`: +2 exports (`AppResolver`, `StartAppEntry`).

**API exported:**
- `StartAppEntry(name, launch_name, process_name)` con `is_appsfolder` property.
- `AppResolver(ttl_seconds=300.0)` con métodos:
  - `entries()` → cached snapshot
  - `display_names()` → raw display names
  - `known_app_names()` → normalised lowercase
  - `find_by_name(raw)` → exact / substring / difflib fallback
  - `resolve_launch(raw)` → launch_name (exe path o `shell:appsfolder\\<AppID>`)

**Hard rules preserved:**
- `_ALIASES = {}` no existe (descarte explícito; localised names vienen de OS).
- `_norm` Unicode-correct: strip Latin diacritics + NFC restore para CJK.
- TTL 300s para no martillar PowerShell.

**Validation:**
- Imports ok.
- `_norm('Configuración')` → `'configuracion'` ✅
- `_norm('Hello World!')` → `'hello world'` ✅
- `is_appsfolder` correcto para `shell:appsfolder\\...` y para `.exe`.

**Risk:** zero — módulo standalone, nadie lo usa todavía. Step 3 lo wirea.

### STEP 3 — Lazy installed_apps + appsfolder [DONE]

**Files touched:**
- `src/carter_v3/tools/dispatch.py`:
  - `_app_open` ladder: AppsFolder URI → `explorer.exe` → Popen → cmd /c start.
  - Net: +20 líneas.
- `src/carter_v3/agent.py`:
  - Nuevo parámetro opcional `app_resolver: AppResolver | None`.
  - Nuevo flag `_installed_apps_explicit` para distinguir lista vacía-explícita vs. default.
  - Nuevo método `_resolved_installed_apps()` (lazy load desde Start menu).
  - Nuevo método `_translate_target_to_launch()` (solo aplica para AppsFolder URIs).
  - `_run_turn_inner` usa `installed = self._resolved_installed_apps()` en lugar de `self.installed_apps`.
  - 3 sitios de dispatch para `app_open` ahora pasan por la traducción.
  - Net: +52 líneas.
- `tests/test_agent_integration.py`:
  - Fixture `engine_factory` ahora fuerza `installed_apps=[]` por default para tests deterministas.
  - Net: +5 líneas.

**Behavioural change:**
- Antes: si el usuario decía "abre la calculadora" sin que Calculator estuviera ya corriendo, el resolver no encontraba match (probe ve solo procesos vivos) y caía a `ambiguity_target_unresolved`.
- Ahora: lazy-load `Get-StartApps` la primera vez que un turno necesita resolver target → inventario completo. Match → `app_open` con `target` traducido a `shell:appsfolder\\<AppID>` cuando aplica → dispatcher rutea por `explorer.exe`.
- Tests deterministas: el fixture vacía `installed_apps` por default; tests específicos pasan su lista.

**Key design choices:**
- Traducción solo para AppsFolder URIs (`is_appsfolder == True`). Si el match es un `.exe`, dejamos el target literal y el dispatcher lo encuentra. Esto evita que `"notepad"` se expanda a `Notepad++.exe` o paths con vendor name.
- Lazy: si el caller pasa `installed_apps=...` explícito (incluyendo `[]`), AppResolver no se consulta nunca. Cero impacto en tests/scripted/dry-run.

**Validation:**
- pytest -q: 200 passed (sin regresiones)
- Smoke: AgentEngine sin installed_apps lanza `_resolved_installed_apps()` lazy.

**Risk:** bajo — el lazy load es opt-out vía explicit `installed_apps`, y la traducción es conservadora.

### STEP 4 — Tests focalizados [DONE]

**Files added:**
- `tests/test_app_resolver.py` (NEW): 22 tests.
  - `_norm` Unicode-correct: Latin diacritics, punct collapse, casefold,
    Japanese voiced marks, Korean Hangul preservation, empty.
  - `StartAppEntry.is_appsfolder` para URI / AppID con `!` / .exe / .lnk.
  - `AppResolver` con `Get-StartApps` mockeado: load, find_by_name exact /
    case / substring / diacritic / difflib / no_match, resolve_launch
    (appsfolder vs exe vs passthrough), failure → empty, TTL cache.
- `tests/test_dispatch_audio.py` (NEW): 8 tests.
  - pycaw missing → ok=False con honest message.
  - pycaw mocked: SetMasterVolumeLevelScalar llamado con 0.30 para level=30.
  - Clamp 999 → 1.0.
  - Invalid level → ok=False.
  - Mute true/false escriben y leen back.
  - State mismatch → ok=False (no fake success).
- `tests/test_agent_integration.py` (EDIT):
  - `test_app_open_translates_to_appsfolder_uri_for_store_app`: Calculator
    Store app → explorer.exe + shell:appsfolder.
  - `test_app_open_does_not_translate_when_target_is_already_exe`:
    `"notepad"` no se expande a Notepad++.exe.

**Validation:**
- pytest: **251 passed** (200 → 251, +51 tests).
- hardcode_guard: clean (42 files scanned).

### STEP 5 — Validación pytest + hardcode_guard [DONE]

- `pytest -q tests`: **251 passed**, 0 failed (en 80s).
- `audit/hardcode_guard.py`: **clean (42 files scanned)**.

**Métricas finales:**
- agent.py: **509 líneas** (era 447; cap 700 OK con margen).
- dispatch.py: **515 líneas** (era 442; +73 por audio real + appsfolder ladder).
- verifier.py: **362 líneas** (era 361; +1 por extracción helper, sin regresión).
- app_resolver.py: **197 líneas** (NEW).
- Total `src/carter_v3`: **5138 líneas** (era 4802; +336).
- Tests: **251** (era 200; +51).
- Catálogo público de tools: **32** (sin cambios — nada se añadió).

**Notas de cap:**
- Cap documental `src/carter_v3 ≤ 4500` ya estaba excedido (4802) antes de esta ronda.
- +336 líneas justificadas: nueva capacidad real (audio write+readback,
  inventario universal de Start apps, AppsFolder ladder).
- Cap `agent.py ≤ 700`: cumplido con 191 líneas de margen.

### STEP 6 — Runner live-safe [DONE]

Initial full run después de STEP 5 mostró regresión real:
- el lazy-load de `Get-StartApps` se disparaba siempre que la lista
  `installed_apps` venía vacía;
- eso contaminaba `ResourceResolver` con apps reales del PC del host;
- prompts como "delete my favorite color" o targets en C11 podían
  resolver contra apps Store reales y disparar tools incorrectas;
- el baseline live-safe del runner se degradaba respecto a round 11.

**Causa raíz.** App discovery quedó como default. El contrato dice
opt-in: el inventario real del host nunca debe leerse como side effect
sin que el caller lo pida explícitamente.

**Fix aterrizado en este step:**
- `src/carter_v3/agent.py`:
  - Nuevo flag de constructor `app_discovery: bool = False` (default OFF).
  - `_resolved_installed_apps()` solo consulta `AppResolver.display_names()`
    cuando `installed_apps` está vacío AND `app_discovery is True`.
  - `_translate_target_to_launch()` añade hard-gate inicial
    `if not self.app_discovery: return call`. Sin opt-in, la traducción
    AppsFolder es no-op y el dispatcher recibe el target literal.
- `tests/test_agent_integration.py`:
  - Los dos tests de traducción AppsFolder
    (`test_app_open_translates_to_appsfolder_uri_for_store_app`,
    `test_app_open_does_not_translate_when_target_is_already_exe`)
    ahora pasan `app_discovery=True` explícito porque ese es el contrato
    que ejercitan.
  - El fixture `engine_factory` se mantiene con `installed_apps=[]` y
    sin `app_discovery=True`, así que ningún otro test abre la puerta
    del Start menu real.

**Comportamiento por defecto verificado:**
- `AgentEngine(adapter=...)` sin nada extra → `app_discovery=False`,
  `installed_apps=[]`.
- `_resolved_installed_apps()` devuelve `[]`.
- `_translate_target_to_launch()` devuelve la `ToolCall` sin tocar.
- El runner live-safe (que crea `AgentEngine` sin opt-in) ya no lee
  `Get-StartApps` ni traduce a `shell:appsfolder\\...`.
- Audio real en `system_set_volume`/`system_mute` y soporte AppsFolder
  en `_app_open` siguen disponibles cuando un caller los activa.

**Validación step 6:**
- `python audit/full_matrix_runner.py --mode live-safe --label
  claude_v2_import_round_full --out audit/runs/claude_v2_import_round_full.json`
- métricas: `executed=526`, `passed=525`, `failed=1`, `skipped=128`
  - `global_pass_rate=99.81%`
  - `P1=100%`, `P2=99.46%`, `P3=100%`
  - `category_11_pass_rate=100%`
  - `category_18_pass_rate=100%`
  - `p95_ms=1274.8`, `pre_llm_p95_ms=63.0`
  - `valid_mission_status_rate=100%`
  - `validator_failures={"active_app_policy": 1}`
- Único fallo: `C4.31 "delete my favorite color"`.
  - El LLM responde un mensaje en inglés genérico que usa la palabra
    `preferences` ("stored in your memory or preferences").
  - El validator `active_app_policy` del runner detecta `preferences`
    como token de una ventana real del host (Settings/preferences
    abierta en alguna app del PC) y lo marca como contaminación.
  - Es un flake dependiente del estado del host, NO una regresión por
    el opt-in: Carter no llamó tools, no resolvió targets, y `mission_status`
    fue `trivial`. El validator simplemente vio coincidencia léxica con
    una ventana real abierta del host en ese instante.
- `pytest -q`: **251 passed**.
- `audit/hardcode_guard.py`: **clean (42 files scanned)**.

### STEP 7 — CHANGELOG + RESIDUAL [DONE]

- `CHANGELOG.md`: nueva sección "V2 Import Round 1 (cierre honesto)"
  documenta audio real, app_resolver, AppsFolder launch y la regla
  opt-in del app discovery.
- `RESIDUAL.md`: nueva sección "Round V2 Import (post-cierre)"
  documenta la traducción AppsFolder gateada, el flake de
  `active_app_policy` por estado del host, y los riesgos abiertos
  reales (no se sumó automatización browser/UIA, OCR/VLM siguen
  fuera).

### STEP 8 — Doc sync + baseline truth [DONE]

- Se releyó la evidencia y apareció una contradicción documental:
  - `audit/runs/claude_v2_import_round_full.json` conserva el primer run
    `525/526`.
  - `audit/runs/codex_verify_claude_v2_import_round_full.json` ya existe
    en repo con `526/526`.
- Validación obligatoria ejecutada de nuevo para este cierre:
  - `python -m pytest -q` -> green otra vez; la suite actual sigue en
    **251/251** (12 módulos: 63 + 23 + 20 + 8 + 16 + 13 + 13 + 11 +
    12 + 23 + 27 + 22).
  - `python audit/hardcode_guard.py` -> **clean (42 files scanned)**.
  - `python audit/full_matrix_runner.py --mode live-safe --label
    round_1_1_doc_sync_full --out audit/runs/round_1_1_doc_sync_full.json`
    -> `executed=526`, `passed=526`, `failed=0`, `skipped=128`,
    `global_pass_rate=100.0%`, `P1/P2/P3=100.0%/100.0%/100.0%`,
    `category_11_pass_rate=100.0%`, `category_18_pass_rate=100.0%`,
    `p95_ms=1232.0`, `pre_llm_p95_ms=63.0`,
    `valid_mission_status_rate=100.0%`,
    `validator_failures={}`.
- Conclusión documental correcta:
  - el `525/526` queda como antecedente histórico de un primer run con
    flake dependiente del host;
  - el baseline actual verificable de Round 1 es **526/526**;
  - `CHANGELOG.md` y `RESIDUAL.md` se sincronizan a esa verdad.
- Artefactos temporales detectados en `audit/runs/`:
  - screenshots generados por runners (`4963fc4603ea_screenshot.png`,
    `aa106c47bbcd_screenshot.png`, y equivalentes de runs previos).
  - No se borró nada: se preservan como evidencia bruta del runner y esta
    ronda es solo de cierre documental.
