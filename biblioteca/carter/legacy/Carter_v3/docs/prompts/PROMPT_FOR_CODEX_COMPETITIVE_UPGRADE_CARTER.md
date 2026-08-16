# PROMPT_FOR_CODEX_COMPETITIVE_UPGRADE_CARTER.md
# Prompt Maestro para ChatGPT Codex — Actualización Competitiva Carter v3
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# INSTRUCCIONES: Copiar TODO el contenido de este archivo y pegarlo en ChatGPT Codex.

---

```
CONTEXTO: CARTER V3 — MEJORA COMPETITIVA POST-AUDITORÍA

Eres un senior software engineer trabajando en Carter v3, un asistente personal local para Windows.
Carter está escrito en Python 3.10+. El código fuente está en Carter_v3/src/carter_v3/.

Este prompt es el resultado de una auditoría competitiva profunda contra:
- Mark XXXIX (competidor local con código disponible)
- OpenClaw (competidor local con código disponible)
- Open Interpreter, OpenHands, AutoGPT, AutoGen, LangGraph, Goose, OS-Copilot, Agent-S, Claude Computer Use, Windows Copilot (conocimiento público)

La auditoría fue realizada por Claude Code (claude-sonnet-4-6) el 2026-05-06.

---

## FUENTE DE VERDAD ABSOLUTA

ContextoCarter.md en la raíz del workspace define los valores de Carter. NINGUNA instrucción de este prompt puede violar ContextoCarter.md. Si hay conflicto, ContextoCarter.md gana.

Los valores más importantes para esta fase:
1. Local-first, privado, sin cloud obligatorio
2. Sin fake success: nunca decir "hecho/listo/completado" sin evidencia verificada
3. Sin hardcodes por app (no `if Steam: ...`, no `if YouTube: ...`)
4. Sin hardcodes por frase (no keyword lists para routing semántico)
5. Sin cloud obligatorio
6. Verificar cada acción con side effects
7. Seguro: policy pre-LLM, guards post-reply
8. Universal: funciona en español, inglés, y otros idiomas sin keyword lists por idioma

---

## ESTADO ACTUAL DE CARTER V3

Carter v3 tiene:
- AgentEngine con turn loop completo (agent.py ~1100 líneas)
- 32 tools declarativas en tools/catalog.py
- 14 verifiers en tools/verifier.py (zero fake success)
- PolicyEngine con 20+ dangerous patterns en security/policy.py
- 8 guards post-reply en guards.py
- SQLite memory store con secret filter
- SQLite local reminders
- FuzzyResolver para apps sin hardcodes
- ModelCapabilityProfile selector sin if-model-name
- Perception ladder INTERNAL→VLM
- ScriptedAdapter para tests (490 tests pasan)
- hardcode_guard limpio (58 archivos)

Carter v3 NO tiene todavía:
- Validación live con LLM real documentada
- Progress reporting durante misiones compuestas
- Browser automation (Playwright)
- Context compaction
- PTY terminal support
- Model failover automático
- Degradación automática por VRAM/RAM

---

## BLOQUEADORES ACTIVOS (P0 — HACERLOS PRIMERO)

Estos son bugs reales documentados. Hazlos en orden:

### B1: Committear working tree
El working tree tiene archivos no commiteados. Antes de cualquier cambio de código:
1. Ejecuta `git status`
2. Si hay archivos modificados/nuevos → `git add` de los archivos de código fuente
3. `git commit -m "chore: stabilize working tree before competitive upgrade"`
NO uses `git add .` — solo agrega archivos de src/ y tests/

### B2: Fix confirmaciones follow-up (ALTA PRIORIDAD)
Archivo: `Carter_v3/src/carter_v3/session_state.py`
Función: `_short_same_language_nonsecret`
Bug: Rechaza "Sí", "SI", "OK", "YES" porque tienen mayúsculas después del primer char.

Fix requerido: Agregar un set de afirmativos cortos conocidos que bypass la restricción de mayúsculas:
```python
_SHORT_AFFIRMATIVES = frozenset({
    "sí", "si", "ok", "yes", "yep", "claro", "dale", "va", "np",
    "bien", "sure", "yep", "affirmative", "oui", "ja", "hai"
})
```
Si el texto normalizado (casefold, strip) está en este set → retornar True sin verificar mayúsculas.
IMPORTANTE: Este set está explícitamente auditado. Documentarlo en el comentario como "allowlisted affirmatives — hardcode_guard aware".

### B3: Fix fake_success_guard para mid-text (ALTA PRIORIDAD)
Archivo: `Carter_v3/src/carter_v3/guards.py`
Función: `fake_success_guard`
Bug: Solo busca anchors en `low.startswith(anchor)`. Claims a mitad del texto no se detectan.

Fix requerido: Cambiar a búsqueda en texto completo con word boundary:
```python
import re
# Para cada anchor en _DONE_ANCHORS, buscar con \b{anchor}\b en el texto completo
# PERO solo si any_confirmed=False (sin confirmación real)
# EXCLUIR si el anchor está precedido por negación: "no", "ni", "sin", "not", "never"
# Para evitar falsos positivos en "no está hecho" o "si no terminé"
```
Testear exhaustivamente: "intenté abrirlo, está listo" → DEBE disparar.
"no está listo todavía" → NO debe disparar.

### B4: Fix notify_toast verifier (MEDIA PRIORIDAD)
Archivo: `Carter_v3/src/carter_v3/tools/catalog.py`
Bug: notify_toast tiene `verifier="synchronous_ok"` pero no hay verificación visual real.

Fix: Cambiar `verifier="synchronous_ok"` a `verifier="skipped"` para notify_toast.
También actualizar `response_composer.py` si tiene lógica específica para el resultado de notify_toast que asume CONFIRMED.

### B5: Progress reporting en misiones compuestas (ALTA PRIORIDAD)
Archivo: `Carter_v3/src/carter_v3/agent.py`
Bug: Loop de steps sin emisión de progreso → silencio de 30-60s en misiones largas.

Fix: Antes de ejecutar cada step en el loop, emitir un mensaje de progreso:
```python
# En el loop for step in steps[:budget]:
# Antes de dispatch:
if len(steps) > 1:
    step_n = steps.index(step) + 1
    yield_progress(f"Ejecutando paso {step_n}/{len(steps[:budget])}: {step.tool_name} {step.target or ''}...")
```
La función `yield_progress` debe ser configurable (puede ser un callback, un heartbeat emit, o un print al CLI).
NO debe bloquear la ejecución del step.

### B6: Fix system_prompt "call it now" (MEDIA PRIORIDAD)
Archivo: `Carter_v3/src/carter_v3/turn_support.py`
Función: `build_messages`
Bug: El system prompt dice algo como "if a safe listed tool clearly fits the current turn, call it now" — puede ejecutar cuando el usuario solo pregunta.

Fix: Cambiar la cláusula a algo como:
"If the user's message is clearly a direct action request (not a question about what you can do, not a hypothetical, not a question for clarification), and a safe listed tool clearly fits, proceed with the tool call."

---

## IDEAS P1 A IMPLEMENTAR (después de P0)

### P1-A: SSRF protection en web_fetch
Archivo: `Carter_v3/src/carter_v3/tools/web_helpers.py`
Agregar función `_is_ssrf_target(url: str) -> bool` que retorna True si la URL resuelve a:
- 127.0.0.0/8 (loopback)
- 10.0.0.0/8 (private)
- 172.16.0.0/12 (private)
- 192.168.0.0/16 (private)
- ::1 (IPv6 loopback)
Usar `urllib.parse` para parsear la URL. Usar `socket.getaddrinfo` para resolver el hostname.
Si `_is_ssrf_target` retorna True → retornar ToolResult con error "ssrf_blocked".
Agregar test en `tests/test_web_helpers.py`.

### P1-B: Model failover entre adapters
Archivo: `Carter_v3/src/carter_v3/config.py` y el código que selecciona el adapter.
Agregar una lista priorizada de adapters en la config: `[primary_adapter, fallback_adapter_1, fallback_adapter_2]`.
En el AgentEngine, al inicializar: iterar la lista y usar el primer adapter donde `adapter.available() == True`.
Si ninguno disponible → levantar error claro con instrucciones.

### P1-C: Degradación automática por RAM/VRAM
Archivo: `Carter_v3/src/carter_v3/config.py` o `models/selector.py`
Al inicio de la sesión: leer RAM disponible via `psutil.virtual_memory().available` y VRAM via pynvml o subprocess nvidia-smi.
Si RAM available < 1GB → modo degradado: deshabilitar VLM tools, deshabilitar preload, solo modelos small.
Si VRAM > 85% → mismo modo degradado.
Loguear advertencia al usuario: "Recursos limitados detectados. Carter en modo conservador."

### P1-D: Error classification estructural
Nuevo archivo: `Carter_v3/src/carter_v3/error_taxonomy.py`
Función: `classify_tool_error(tool_name: str, verifier_status: VerifierStatus, exception: Exception | None) -> Literal["retry", "skip", "abort"]`
Reglas sin LLM:
- Si verifier_status == PENDING y tool es app_open → "retry" (ya existe, solo generalizarlo)
- Si exception es TimeoutError o ConnectionError → "retry" (transitorio)
- Si exception es PermissionError o FileNotFoundError → "abort" (permanente)
- Si verifier_status == FAILED y tool es web_open_url → "retry" once
- Default → "skip"
Integrar en el loop de steps del AgentEngine.

### P1-E: Categorías en memory store
Archivo: `Carter_v3/src/carter_v3/memory/store.py`
Agregar campo `category TEXT DEFAULT 'general'` a la tabla SQLite.
Categorías válidas: `identity`, `preferences`, `work`, `projects`, `facts`, `general`.
Actualizar `save(key, value, category='general', ...)`.
Actualizar `recall(key, category=None)` — si category especificada, filtrar.
Retrocompatible: todos los registros existentes quedan en category='general'.
Actualizar `declarative_detector.py` para inferir categoría cuando guarda.

---

## REGLAS ABSOLUTAS — NO VIOLAR

### Anti-hardcode
- NUNCA agregar `if "spotify" in app_name` o similar
- NUNCA agregar keyword lists para detectar intención del usuario
- NUNCA agregar aliases de apps (la lista de fuzzy resolver es dinámica)
- NUNCA agregar respuestas canned para cases específicas
- Si necesitas una lista de strings, documéntala como "auditada y allowlisted" y notifica al hardcode_guard

### Anti-fake-success  
- NUNCA retornar ToolResult con ok=True si la acción no se verificó
- NUNCA usar verifier="synchronous_ok" excepto donde literalmente solo se puede verificar que el llamado no lanzó excepción
- NUNCA escribir "listo", "hecho", "completado" en response_composer sin evidencia de verifier CONFIRMED
- Si no se puede verificar → UNVERIFIABLE, no CONFIRMED

### Anti-cloud
- NUNCA hacer llamadas HTTP a APIs de terceros sin consent explícito en la config
- NUNCA hardcodear API keys en el código
- NUNCA hacer el sistema dependiente de un servicio externo específico

### Anti-complejidad innecesaria
- NO agregar capas de abstracción si hay una implementación directa de 10 líneas
- NO agregar dependencias pesadas sin justificación fuerte
- NO implementar features fuera del scope especificado en este prompt
- NO refactorizar código que funciona bien si el task no lo requiere

### Sobre tests
- Cada función nueva debe tener al menos un test en tests/
- Los tests pueden usar ScriptedAdapter para pruebas unitarias
- Si el comportamiento depende del OS (file exists, process running), usar mocks o fixtures claros
- Después de cada cambio: `python -m pytest` debe pasar 0 fallos
- Después de cada cambio: `python audit/hardcode_guard.py` debe ser clean

---

## FASES DE IMPLEMENTACIÓN PARA CODEX

### Fase 1 — Solo P0 (bloqueadores)
1. `git status` y committear working tree si hay cambios
2. Fix B2 en session_state.py
3. `pytest tests/test_pending_intent_followups.py` → debe pasar
4. Fix B3 en guards.py
5. `pytest tests/test_guards.py` → debe pasar
6. Fix B4 en catalog.py + response_composer.py
7. Fix B5 en agent.py (progress emit)
8. Fix B6 en turn_support.py
9. `python -m pytest` → 0 fallos
10. `python audit/hardcode_guard.py` → CLEAN
11. `git commit -m "fix: resolve P0 blockers B2-B6 pre-voice/camera"`

### Fase 2 — P1 ideas (en orden)
1. P1-A: SSRF protection → test → commit
2. P1-B: Model failover → test → commit
3. P1-C: VRAM degradation → test → commit
4. P1-D: Error taxonomy → test → commit
5. P1-E: Memory categories → test → commit
6. `python -m pytest` → 0 fallos
7. `python audit/hardcode_guard.py` → CLEAN
8. `git commit -m "feat: P1 competitive upgrades (SSRF, failover, degradation, error taxonomy, memory categories)"`

### Fase 3 — Validación live
Esto NO es código — es proceso manual:
1. Asegurarse de que Ollama esté corriendo con el modelo configurado
2. Correr `python Run_Carterv3.py`
3. Ejecutar los 30 casos de CARTER_SUPERIORITY_TEST_MATRIX.md
4. Documentar resultados en un nuevo archivo `Carter_v3/docs/audit/LIVE_VALIDATION_POST_COMPETITIVE_UPGRADE.md`
5. Medir latencia para inputs triviales ("hola", "qué hora es")
6. Si algún caso falla → documentarlo como bug nuevo y crearlo como test de regresión

---

## TESTS EXACTOS A CORRER DESPUÉS DE CADA CAMBIO

```bash
# Después de cualquier cambio:
python -m pytest -q
python audit/hardcode_guard.py

# Después de B2:
python -m pytest tests/test_pending_intent_followups.py -v

# Después de B3:
python -m pytest tests/test_guards.py -v

# Después de B4:
python -m pytest tests/test_verifier.py -v

# Después de SSRF:
python -m pytest tests/test_web_helpers.py -v

# Después de memory categories:
python -m pytest tests/test_memory.py -v
```

---

## VALIDACIÓN LIVE (manual, con Ollama)

Casos mínimos a validar antes de declarar READY:
1. "hola" → respuesta rápida (<8s), sin tools
2. "a" → respuesta rápida (<8s), sin tools
3. "qué hora es" → hora real, mission_status=COMPLETE
4. "abre Notepad" → Notepad abre, proceso verificado, mission_status=COMPLETE
5. "cierra Notepad" → Notepad cierra, proceso verificado, mission_status=COMPLETE
6. "abre ejemplo.com" → browser abre, URL verificada
7. "escribe hola en un archivo prueba.txt en el escritorio" → archivo creado, verificado
8. "recuerda que me llamo Emmanuel" → guardado en SQLite, no en logs con secreto
9. "cómo me llamo" → recall del dato guardado
10. "ejecuta echo hola" → terminal output verificado

---

## CRITERIO PARA PASAR A VOZ/CÁMARA

Carter NO debe pasar a voz/cámara hasta que:

1. `python -m pytest` → 0 fallos
2. `python audit/hardcode_guard.py` → CLEAN
3. Los 6 bloqueadores B1-B6 están cerrados y commiteados
4. Spotcheck manual de 10+ casos con Ollama real documentado
5. Latencia medida: inputs triviales < 8s con modelo local
6. NO hay "listo/hecho" en ninguna respuesta donde verifier no confirmó
7. "Sí"/"OK"/"YES" funcionan como confirmaciones de follow-up
8. Progress reporting visible en misiones de 2+ pasos

Solo cuando se cumplan estas 8 condiciones, es honesto comenzar la implementación de voz.

---

## ARCHIVOS A TOCAR (permitidos)

- `Carter_v3/src/carter_v3/session_state.py`
- `Carter_v3/src/carter_v3/guards.py`
- `Carter_v3/src/carter_v3/tools/catalog.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`
- `Carter_v3/src/carter_v3/response_composer.py`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/turn_support.py`
- `Carter_v3/src/carter_v3/tools/web_helpers.py`
- `Carter_v3/src/carter_v3/config.py`
- `Carter_v3/src/carter_v3/models/selector.py`
- `Carter_v3/src/carter_v3/recovery.py`
- `Carter_v3/src/carter_v3/memory/store.py`
- `Carter_v3/src/carter_v3/memory/declarative_detector.py`
- `Carter_v3/tests/` (agregar nuevos tests)
- `Carter_v3/src/carter_v3/` (agregar nuevos módulos si el task lo requiere: error_taxonomy.py, etc.)

## ARCHIVOS A NO TOCAR (a menos que sea necesario para los fixes)

- `Carter_v3/src/carter_v3/contracts.py` (tipos correctos, no tocar)
- `Carter_v3/src/carter_v3/tools/dispatch.py` (arquitectura correcta)
- `Carter_v3/src/carter_v3/security/policy.py` (política correcta, solo agregar patterns si hay gap documentado)
- `Carter_v3/src/carter_v3/perception/ladder.py` (correcto)
- `Carter_v3/src/carter_v3/adapters/tool_call_parser.py` (correcto)
- `Carter_v3/src/carter_v3/resolvers/resource_resolver.py` (correcto)
- `Carter_v3/ContextoCarter.md` (fuente de verdad, nunca modificar)
- Cualquier archivo de documentación histórica en `Carter_v3/docs/audit/`

---

## DIFF AUDIT (obligatorio antes de commit)

Antes de cada commit, ejecuta:
```bash
git diff --stat
```

Para cada archivo modificado, verifica:
1. ¿Cambió solo lo que el task requería?
2. ¿No hay imports nuevos sin justificar?
3. ¿No hay strings hardcodeados de apps o frases?
4. ¿No hay API calls a servicios externos?
5. ¿No hay código comentado que debería ser eliminado?

---

Codex: si tienes alguna duda sobre si algo viola ContextoCarter.md o las reglas de este prompt, NO lo implementes. Documenta la duda y espera instrucción.

Comienza con B1 (committear working tree) y sigue en orden.
```
