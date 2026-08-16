# LIVE_RUNTIME_CYCLE_3_REPAIR_PLAN

Máximo 4 cambios de código (universales, sin hardcodes semánticos, sin `looks_*` de intención, sin branches por palabras del usuario).

Fuente de verdad:
- `ContextoCarter.md`
- `LIVE_RUNTIME_POST_CLEANUP_BLOCKERS.md`
- `LIVE_SAFE_RUNTIME_CLOSURE_REPORT.md`

---

## Cambio 1 (request_patterns.py): endurecer referencia deíctica + path Windows estructural
**Qué cambiar**
1) Ajustar `DEICTIC_REFERENCE` para que no matchee palabras genéricas que terminan en `la/lo/los/las` (evitar falsos “deictic_shaped” que disparan rutas de acción para inputs triviales/typos).
2) Reintroducir `extract_windows_path()` como extracción estructural de forma `C:\...\archivo.ext` (solo por shape).
3) Usar `extract_windows_path()` en:
   - `extract_action_target_span()` para evitar resolver target desde paths;
   - `synthesise_structural_tool_call()` para generar `ToolCall(name="filesystem_read_text", arguments={"path": ...})`.

**Por qué es universal**
- No depende de “lee/alarma/pausala/HGOla” como frase; depende de gramática/forma (path absolute Windows).

---

## Cambio 2 (agent.py): activar looks_action por presencia estructural de path Windows
**Qué cambiar**
- Importar `extract_windows_path` y añadir `or bool(extract_windows_path(user_text))` dentro del cálculo de `looks_action`.

**Por qué es universal**
- Activación por evidencia estructural (path) y no por palabra.

---

## Cambio 3 (turn_support.py): incluir filesystem_read_text en el tool set cuando hay path Windows
**Qué cambiar**
- En `select_tools()`, si `extract_windows_path(user_text)` no está vacío, incluir `filesystem_read_text` en `preferred`.

**Por qué es universal**
- Tool set derivado de capacidades/selección estructural, no routing por intención semántica.

---

## Cambio 4 (guards.py): bloquear claims temporales futuras sin confirmación de tool
**Qué cambiar**
- Extender `fake_success_guard()` con un detector estructural de “claim con hora futura” basado en un regex de tiempo (AM/PM y/o HH:MM), disparando solo cuando:
  - `any_confirmed == False`
  - y el reply contiene un patrón temporal.

**Por qué es universal**
- Es una regla de honestidad/verificación (tiempo futuro sin tool confirmado), no una lista de frases ni un detector por palabra “alarma”.

---

Estrategia de ejecución:
- Implementar cambios 1..4 secuencialmente.
- Después de cada cambio:
  - `python -m pytest tests/test_no_semantic_hardcodes.py -v`
  - `python audit/hardcode_guard.py`
  - correr tests relevantes (prioridad a los módulos afectados por el cambio).
- Si `hardcode_guard` falla, revertir inmediatamente ese archivo antes de continuar.

