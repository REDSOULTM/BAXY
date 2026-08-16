# Revisión Manual del Trabajo de Gemini

**Fecha**: 2026-04-29
**Revisor**: Claude Opus 4.7 (sesión anterior)
**Rango revisado**: commits `29877f3..c1fad81` (17 commits) + cambios sin commit
**Branch**: `rebuild/v2-from-scratch`

Esta revisión es **manual, sin agentes**. Cada commit fue inspeccionado con `git show` y verificado contra el código real.

---

## Estado de Validación

- ✅ pytest local antes de Gemini: **815 passed** (con mi fix de fixture)
- ⚠️ pytest después de Gemini: **NO ejecutado** (usuario jugaba)
- ⚠️ probe_all_tools.py después de Gemini: según `GEMINIWORK.MD`, **159/165 (96%)** — fallos atribuidos a entorno (Office, file locks) + 2 fallos lógicos (`UNIV-3`, `S25-INTENT-3`)
- ⚠️ probe_text_hardening.py: NO ejecutado

**Hay que correr la validación full antes de declarar nada cerrado.**

---

## Resumen por Commit (cronológico)

### 1. `69e0407` — Test isolation helpers ✓ LIMPIO
- Agrega `clear_all_hooks()` a `event_bus.py`.
- Agrega `reset_policy_state()` a `policy.py`.
- Crea `tests/conftest.py` con fixture autouse `isolate_global_state`.
- **Riesgo**: bajo. Solo helpers y reset entre tests.
- **Nota**: Mi fix en `test_text_agent_regressions.py` (fixture `_auto_approve_high` con monkeypatch) sigue siendo necesario porque el conftest **no setea env vars**, solo limpia hooks/policy/cache. Está bien que coexistan.

### 2. `442884a` — Eliminar mutación permanente del SO ✓ LIMPIO
- Reemplaza `_apply_ollama_env_permanently()` con `_apply_ollama_env_locally()`.
- **Elimina `setx`** (ya no escribe al registro de Windows).
- **Elimina `taskkill /F /IM ollama.exe`** (ya no mata Ollama existente).
- Si Ollama está corriendo sin optimizaciones, ahora solo **emite warning** a stderr.
- **Riesgo**: bajo. Buen cambio. Carter ya no contamina el sistema operativo.
- **Verificación pendiente**: probar que `ollama serve` se levanta correctamente cuando NO está corriendo.

### 3. `db5fa23` — Centralizar config (parte 1) ⚠️ REVISAR INTERACCIÓN CON TESTS
- Agrega `auto_approve_high`, `auto_approve_critical`, `memory_dir`, `llm_base_url`, `llm_api_key`, `llm_model` a `CarterSettings`.
- `policy.py` ahora lee `get_settings().auto_approve_high` en vez de `os.getenv`.
- `OpenAICompatAgentBackend.__init__` lee de settings.
- **Riesgo**: medio. Cambio el origen de verdad de env-direct → cached settings.
- **Cuidado**: cualquier test que haga `os.environ["CARTER_AUTO_APPROVE_HIGH"] = "1"` **DESPUÉS** de un `get_settings()` previo verá la cache vieja. El conftest llama `reset_cache()` antes de cada test, lo que mitiga esto, pero solo funciona si el setenv del test ocurre **antes** del primer `get_settings()` del test.
- **Verificar**: que `test_policy_fase3.py` siga pasando (sus tests setean env y luego llaman policy).

### 4. `9fa4c53` — Centralizar config (parte 2) ⚠️ MIRAR
- Agrega `workspace_dir`, `gguf_path`, `draft_gguf_path`, `draft_mode`, `draft_tokens` a `CarterSettings`.
- Cambia `_auto_backend()`, `detect_gguf_path()`, etc., para leer de settings.
- **Riesgo**: medio. Mismo patrón que (3).
- **Verificar**: que `_auto_backend()` siga eligiendo el backend correcto. Usuario está en `llamacpp`.

### 5. `8ea9a83` — Memory hardening (parte 1) ⚠️ COSMETICA SUCIA
- Reemplaza muchos `except Exception: pass` por `except Exception as exc: _log_memory_warning(exc)` en `memory.py`.
- **Bug cosmético**: varios bloques quedaron con líneas en blanco huérfanas (corregidas en commit siguiente).
- **Riesgo**: bajo. Cambia "fail silently" por "log + fail". Bueno.

### 6. `06dd12a` — Memory hardening (parte 2) ✓ CLEANUP
- Limpia las líneas en blanco huérfanas del commit anterior.
- Agrega contexto al log: `_log_memory_warning(exc, "save_fact")`.
- **Riesgo**: ninguno.

### 7. `368f65c` — Tool timeout warnings ✓ LIMPIO
- Reemplaza `except Exception: pass` por warnings con stderr en `agent.py`.
- Agrega warning cuando un tool excede timeout y puede haber dejado thread huérfano.
- **Riesgo**: ninguno. Solo logs.

### 8. `619a698` — Docs ✓ LIMPIO
- Actualiza `.env.example` con nuevas variables.
- Agrega entrada al "Plan de trabajo".

### 9. `c1fad81` — Test fix ✓ LIMPIO
- En `test_medium_priority.py::TestOmniParserGraceful`, genera PNG válido con PIL en vez de bytes truncados `b"\x89PNG\r\n\x1a\n"`.
- **Riesgo**: ninguno.

### 10. `3994bd8` — Nuevo invariant 🔴 BUG GRAVE
- Agrega `_invariant_live_query_redirect` en `invariants.py`.
- Detecta queries de pantalla activa/ventanas y redirige `memory_recall` → ...
- **🔴 PROBLEMA**: usa **tool names que NO EXISTEN** en `tools.py`:
  - `desktop_screenshot_analyze` ❌ (real: `desktop_screenshot`)
  - `window_get_active` ❌ (real: `window_inspect_active`)
  - `window_list` ✓ (este sí existe)
- **Si este invariante dispara, el agent intentará llamar tools inexistentes → fallo**.
- **Acción requerida**: corregir nombres a `desktop_screenshot` y `window_inspect_active`, o agregar tools nuevos al catálogo si Gemini quería específicamente esa funcionalidad.
- **Test pendiente**: verificar si algún test cubre este invariante (no lo hay en mi `test_text_agent_regressions.py`).

### 11. `dedeffb` — Probes con `-u` ✓ LIMPIO
- Agrega `python -u` (unbuffered) en `run_text_closure_gate.py` para evitar el problema que tuve con stdout vacío.

### 12. `b8d638a` — GPU full-power mode ⚠️ DECISIÓN DEL USUARIO
- `run_carter_gpu.ps1` ahora setea `CARTER_AUTO_APPROVE_HIGH=1` Y `CARTER_AUTO_APPROVE_CRITICAL=1`.
- Imprime un warning rojo sobre "FULL POWER MODE".
- Tests nuevos en `test_policy_fase3.py` y `test_power_capability.py` cubren ambos paths.
- **Riesgo**: medio. Auto-aprueba shutdown/reboot/format en GPU mode. Es decisión consciente del usuario.
- **Verificar**: que el usuario realmente quiere shutdown sin confirmar. Si no, revertir el `CARTER_AUTO_APPROVE_CRITICAL=1`.

### 13. `cce53c0` — `GEMINI.md` ✓ DOCS
- Crea `GEMINI.md` con instrucciones del proyecto para Gemini CLI.

### 14. `53d12a5` — Dialog resolver ⚠️ MÓDULO NUEVO GRANDE
- Agrega `src/carter_v2/capabilities/_dialogs.py` (538 líneas).
- Agrega `tests/test_dialog_helpers.py` (71 líneas).
- Usado por `steam.py`: `from ._dialogs import activate_dialog_primary_action, find_popup_window, select_dialog_option`.
- **Riesgo**: medio-alto. 538 líneas nuevas no auditadas en detalle. Lógica compleja de UIA + matching semántico.
- **Acción**: requiere revisión profunda independiente.

### 15-17. `856ddaf`, `8c2f3a4`, `4d9de81` — Docs/conftest cache ✓ LIMPIO
- Docs y `reset_cache()` agregado a `conftest.py`. Necesario por (3).

---

## Cambios SIN COMMIT (en working tree)

### `Carter_v2/probe_all_tools.py`
- Agrega chequeo de `backend.supports_tools` (rechaza modelos de visión como llava).
- Mensajes en español. **Hay caracteres mojibake**: `visiÃ³n`, `vÃ¡lidos` (encoding mal). Limpiar antes de commitear.
- **Riesgo**: bajo. Buen check.

### `Carter_v2/probe_text_hardening.py`
- Mismo chequeo `supports_tools`. Sin mojibake.
- **Riesgo**: ninguno.

### `Carter_v2/probe_assets/sample.docx`, `Carter_v2/probe_assets/sample.png`
- Modificados (probablemente por probe runs). Ignorables.

### `.claude/settings.local.json`
- Permission para `Bash(python probe_all_tools.py)`. Trivial.

---

## Archivos NO TRACKEADOS Relevantes

- `Carter_v2/GEMINIWORK.MD` — bitácora de Gemini (puede mantenerse o eliminarse).
- `Carter_v2/scripts/inspect_vision.py` — script utilitario nuevo. No revisado.
- Mucho ruido de probes: `probe_*.txt`, `probe_*.json`, `probe_*.pdf`, etc. Limpiar.

---

## Bugs / Riesgos Identificados (prioridad)

### 🔴 CRÍTICO
1. **`_invariant_live_query_redirect` usa tool names inexistentes** (`desktop_screenshot_analyze`, `window_get_active`).
   Archivo: `src/carter_v2/turn/invariants.py:153-160`.
   Fix: cambiar a `desktop_screenshot` y `window_inspect_active`, o agregar los tools al catálogo.

### 🟡 ALTO
2. **No hay tests para el nuevo invariant `live_query_redirect`**. Agregar a `test_text_agent_regressions.py`.
3. **`_dialogs.py` (538 líneas) no fue auditado en profundidad**. Requiere revisión por experto en UIA.
4. **Caracteres mojibake en `probe_all_tools.py`** (sin commit). Corregir antes de commitear.

### 🟢 MEDIO
5. **`CARTER_AUTO_APPROVE_CRITICAL=1` en `run_carter_gpu.ps1`**: confirmar con usuario que quiere auto-aprobar shutdown/reboot.
6. **Validación pendiente**: pytest full + probe_all + probe_text_hardening con la combinación de cambios actual.
7. **`UNIV-3` y `S25-INTENT-3` siguen fallando** según GEMINIWORK.MD (96% en probe_all). No regresión, pero no cerrado al 100%.

---

## Plan de Acción para Opus 4.7

### Paso 1: Validar baseline actual
```powershell
Set-Location "c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\Carter_v2"
python -m pytest tests/ -q --tb=short
```
Confirmar que sigue en 815+ passed (esperado: ~819 con tests nuevos de policy/dialog).

### Paso 2: Fix CRÍTICO del invariant
Editar `src/carter_v2/turn/invariants.py` líneas ~153-160:
```python
# Route based on whether they ask for the active window or screen
if "pantalla" in lower or "screen" in lower or "monitor" in lower or "display" in lower or "viendo" in lower:
    net_tool = "desktop_screenshot"          # was: "desktop_screenshot_analyze"
elif "lista" in lower or "todas" in lower or "all" in lower or "list" in lower:
    net_tool = "window_list"
else:
    net_tool = "window_inspect_active"       # was: "window_get_active"
```

### Paso 3: Agregar test de regresión para el invariant
En `tests/test_text_agent_regressions.py` agregar clase `TestLiveScreenQueryRedirect` con casos como:
- `"qué tengo en pantalla?"` → debe redirigir a `desktop_screenshot`
- `"cuál es mi ventana activa?"` → debe redirigir a `window_inspect_active`
- `"muéstrame todas las ventanas"` → debe redirigir a `window_list`

### Paso 4: Limpiar mojibake
Editar `probe_all_tools.py` líneas con `visiÃ³n` → `visión`, `vÃ¡lidos` → `válidos`.

### Paso 5: Auditoría profunda de `_dialogs.py`
Lectura completa de las 538 líneas. Verificar:
- No hay code injection en queries UIA.
- Manejo de Unicode en `unicodedata.normalize`.
- Timeouts y retries son razonables.
- No hay coordenadas hardcoded.

### Paso 6: Validación final
```powershell
python run_text_closure_gate.py
```
Si pasa: declarar Carter v2 estable post-Gemini.

### Paso 7 (opcional): atacar `UNIV-3` y `S25-INTENT-3`
Si el usuario quiere 100% en probe_all, investigar estos 2 fallos lógicos (no son regresiones de Gemini, son bugs de qwen3:8b mismo).

---

## Veredicto

**Trabajo de Gemini: 75% bueno, 20% requiere review, 5% bug claro.**

Lo bueno:
- Eliminó setx/taskkill (gana real para seguridad).
- Centralizó config razonablemente.
- Mejoró logging de errores silenciosos.
- Agregó tests para los cambios de policy/power.
- Documentación actualizada.

Lo malo:
- **Inventó tool names que no existen** en el invariant nuevo (regresión potencial).
- No corrió validación full después de sus cambios.
- 538 líneas nuevas en `_dialogs.py` sin revisión profunda.
- Mojibake en mensajes de probe (encoding).

**No revertir.** Los commits buenos superan a los problemáticos. Solo aplicar el fix del invariant y agregar el test de regresión.

---

## Comandos rápidos para Opus

```powershell
# Verificar estado
git log --oneline 29877f3..HEAD
git status --short

# Validar
Set-Location Carter_v2
python -m pytest tests/ -q --tb=short
python -m pytest tests/test_text_agent_regressions.py -v

# Fix invariant + test (manualmente con Edit tool)

# Validación final
python probe_text_hardening.py
python probe_all_tools.py
```
