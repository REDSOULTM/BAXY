# Plan: vram4 único + Modos de accesibilidad

Decisiones del usuario (2026-05-26):
- **A primero, luego B.** Simplificar a vram4-único y verificar, después construir los modos.
- **vram4 único, sin selector.** Borrar vram3/6/8/12/16 del código; vram4 (E2B-Q4) es el único perfil real.
- **No tocar archivos GGUF.** Solo código; los modelos en disco quedan intactos.
- **UI React: sí tocar + rebuild.**
- **Modos: capa base primero, luego `movilidad` primero.** 3 perfiles `normal`/`no_vidente`/`movilidad`, activables por voz (LLM/embeddings, multilingüe) + config persistente.
- **Medición: yo la lógica + lo que no emite input físico; el usuario lo físico.**

---

## PARTE A — vram4 como único perfil

### A1. `profiles.py` — colapsar a un solo perfil
- `PROFILES` queda solo con `vram4` (E2B-Q4_K_M, mmproj E2B, ctx 12288, visión ON, voz ON) y `standby` (necesario: apaga el server; la UI lo usa).
- `PROFILE_NAMES = ("vram4", "standby")`.
- `recommend_profile(...)` → siempre `"vram4"` (sin escalera; documentar por qué).
- `_LEGACY_ALIASES`: TODOS los nombres viejos (vram3/6/8/12/16/performance/balanced/light…) → `"vram4"`. Así un `active_profile.txt` viejo no rompe.
- `detect_vram_mb()` se conserva (la UI lo muestra como dato), pero ya no decide perfil.
- Arreglar el docstring contradictorio de `recommend_profile` (decía E4B-Q4/7.3GB; el real es E2B-Q4/3.36GB).
- `get_active_profile` default = vram4 (ya lo es).

### A2. `profile_watcher.py` — neutralizar (no borrar)
- El daemon de auto-downgrade/upgrade no tiene sentido con un solo perfil.
- `WatcherConfig.enabled=False` ya es el default → queda inerte.
- `downgrade_to`/`restore_to` → ambos `"vram4"` (no-op si alguien lo activa).
- Dejar el módulo importable (no romper imports de quien lo referencia).

### A3. UI Python — `ui/main_window.py`, `ui/settings.py`
- Quitar el selector de perfiles (o dejarlo mostrando solo vram4 informativo).
- No romper el resto del panel.

### A4. UI React — `ui_field/src/components/SettingsPanel.tsx`, `App.tsx`, `SubstratePanel.tsx`
- Quitar el selector de perfiles del front.
- `npm run build` en `ui_field/` para regenerar el bundle (`dist/`).

### A5. `server.py`, `config.py`, `chat.py`, `agent_prompt.py`, `domain_tools.py`, `llama_server.py`
- Revisar cada referencia a nombres de perfil; ajustar a vram4-único donde aplique.

### A6. Tests
- `test_profiles_restart.py` y `test_profile_watcher_restart.py`: prueban switching multi-perfil (comportamiento que se elimina) → reescribir a "un solo perfil, sin switching" o marcar obsoletos.
- `test_lazy_vision_resolve.py`, `test_vram_calculator.py`, otros que nombren perfiles borrados → ajustar.
- Verificación: `python -m py_compile` + imports + tests mock-only por archivo (NO `pytest -k` amplio — crashea nativo en Windows; NO tests de input sintético).

### Gate A (antes de pasar a B)
- `from gemma4_agent import profiles, launcher, profile_watcher, server, config` importan OK.
- `get_active_profile().name == "vram4"`; un alias legacy ("balanced") resuelve a vram4.
- Tests tocados pasan (mock-only).
- (Usuario) boot real + UI coherente.

---

## PARTE B — Modos de accesibilidad (después de Gate A)

### B1. Capa base — `gemma4_agent/accessibility.py` (nuevo)
- 3 perfiles: `normal` (vacío, = comportamiento actual), `no_vidente`, `movilidad`.
- Cada uno: `system_hint` (multilingüe, comportamiento NO contenido — anti-enlatados) + flags estructurales:
  - `narrate_all_actions` (no_vidente)
  - `read_screen_on_demand` (no_vidente)
  - `hands_free_only` (movilidad)
  - `confirm_irreversible_spoken` (movilidad)
- Persistencia: `~/.gemma4/active_accessibility_mode.txt` (patrón de `active_profile.txt`).
- Enganche: el `system_hint` del modo se inyecta junto al de mode/persona en `agent.py:462`.

### B2. Activación por voz (multilingüe, sin regex es-only)
- Detección por embeddings (reusa `semantic_router`/`intent_router`) + fallback seguro.
- "activá modo para no videntes" / "no puedo usar las manos" → cambia y persiste, confirmando por voz.

### B3. `movilidad` primero (el más cercano a listo)
- Auditar que toda capacidad del computer-use es alcanzable por voz sin asumir input físico.
- Confirmación hablada sí/no para acciones irreversibles (en vez de diálogo visual).

### B4. `no_vidente` (después)
- `describe_screen` como tool de primera clase (reusa visión multimodal + cascada UIA→OCR→visión).
- Narración garantizada de cada acción al TTS.
- Leer contenido/errores on-demand.

### B5. Eval + informe
- `scripts/accessibility_eval/`: misiones por perfil, evaluadas por estado del SO + presencia de audio en el trace.
- Gates: no_vidente=100% acciones narradas; movilidad=0 pasos que requieran input físico del user; normal sin regresión.
- Informe con fuentes WCAG 2.1/2.2 + ARIA + el dato de los 4GB de VRAM (lo "defendible").

### Fuentes (verificadas esta sesión)
- WCAG 2.2 — https://www.audioeye.com/post/wcag-22/
- WCAG 2.1 success criteria — https://www.levelaccess.com/blog/wcag-2-1-exploring-new-success-criteria/

---

## Límites honestos (no negociables)
- NO corro tests de input sintético (cierran VS Code — lo hace el usuario).
- NO `pytest -k` amplio (crashea nativo en Windows).
- NO borro GGUF.
- NO hardcodes de frases ni keywords por idioma.
- El techo del computer-use sigue siendo apps UIA-ricas (ya medido); se dirá explícito.
