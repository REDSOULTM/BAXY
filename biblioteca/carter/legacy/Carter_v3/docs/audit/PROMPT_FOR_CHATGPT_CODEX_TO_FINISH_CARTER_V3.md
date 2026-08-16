# PROMPT MAESTRO PARA CHATGPT CODEX
# Objetivo: Llevar Carter v3 al 100% real del núcleo texto, pre-voz, pre-cámara
# Fecha de auditoría: 2026-05-06
# Auditado por: Claude Code (claude-sonnet-4-6) sobre código real

---

## INSTRUCCIONES PARA CHATGPT CODEX

Este es un prompt completo con toda la información que necesitas. No preguntes por lo que ya está aquí.

Trabaja en este orden:
1. Lee el contexto del proyecto
2. Lee el resumen de auditoría
3. Implementa los fixes en orden de prioridad
4. Valida después de cada fix con los comandos indicados
5. No declares READY hasta que pasen todos los criterios

---

## CONTEXTO DEL PROYECTO

**Carter** es un asistente personal local tipo Jarvis para Windows, corriendo con modelos LLM locales vía Ollama. Es un agente autónomo con:
- Núcleo texto completo (sin voz ni cámara todavía)
- 32 herramientas declarativas (catálogo en `tools/catalog.py`)
- Verificación real post-acción (no fake success)
- Política de seguridad antes del LLM
- Guardas post-LLM
- Memoria persistente SQLite
- Recordatorios locales SQLite
- Session state con TTL decay

**Ruta del proyecto:** `Carter_v3/src/carter_v3/`
**Tests:** `Carter_v3/tests/`
**Auditoría:** `Carter_v3/audit/`
**Runner:** `Carter_v3/audit/full_matrix_runner.py`

---

## LEY ABSOLUTA: CONTEXTOCARTER.MD

Antes de implementar cualquier cosa, lee `ContextoCarter.md` completo (944 líneas). Este documento define la identidad, valores y comportamiento de Carter. Sus 30 valores son la ley. Cualquier código que lo contradiga debe corregirse.

Valores más críticos:
- **Valor 3:** Carter no miente. Nunca "listo/hecho" sin verificación.
- **Valor 4:** Cada acción con efecto tiene verificación real.
- **Valor 6:** Sin hardcodes por frase/app/idioma.
- **Valor 7:** Sin hacks por marca (Steam, Spotify, WhatsApp, etc.).
- **Valor 15:** Seguridad — bloquear acciones destructivas.
- **Valor 16:** Misiones compuestas con progreso reportado por paso.
- **Valor 24:** Medirse con pruebas reales, no solo tests bonitos.

---

## RESUMEN DE AUDITORÍA (Claude Code, 2026-05-06)

### Estado actual
- **490 tests pasan** con ScriptedAdapter (no ejercitan LLM real)
- **hardcode_guard limpio** — sin marcas ni listas de keywords en runtime
- **540/540 en live-safe-all** — pero con side effects bloqueados (no prueba acción real)
- **Working tree no commiteado** — 202 líneas de diferencia vs. tag oficial

### Lo que funciona bien (NO TOCAR)
- Arquitectura del AgentEngine
- Sistema de guardas (guards.py)
- PolicyEngine con 20+ patterns de seguridad
- VerificationManager con verifiers reales por tool
- MemoryStore SQLite con secret filter
- LocalReminderStore SQLite
- Tool catalog declarativo (32 tools, sin hardcodes de marca)
- Session state con pending_intent, pending_memory_offer, pending_tool_approval

### Bloqueadores identificados (DEBEN CORREGIRSE)

**B1 — Confirmación de follow-up rota**
- Archivo: `Carter_v3/src/carter_v3/session_state.py`
- Función: `_short_same_language_nonsecret()`
- Problema: Rechaza "Sí", "Si", "OK", "YES" por tener mayúsculas (`any(ch.isupper() for ch in text[1:])`)
- Fix: Para tokens de 1-3 chars como "Sí", "OK", "YES", "NO" — relajar la restricción de mayúsculas

**B2 — fake_success_guard solo cubre inicio de reply**
- Archivo: `Carter_v3/src/carter_v3/guards.py`
- Función: `fake_success_guard()`
- Problema: `_DONE_ANCHORS` se verifica solo con `low.startswith(anchor)`. Claims como "Intenté abrir X y está listo" no se bloquean.
- Fix: También verificar `anchor in low` con contexto de "afirmación de completitud" más robusto (ej: " listo." al final)

**B3 — notify_toast marca CONFIRMED sin verificación visual real**
- Archivo: `Carter_v3/src/carter_v3/tools/catalog.py`
- Línea: `ToolSpec("notify_toast", ..., verifier="synchronous_ok")`
- Problema: `synchronous_ok` solo verifica `result.ok=True`. No verifica que Windows mostró la notificación (DND puede estar activo).
- Fix: Cambiar `verifier="synchronous_ok"` a `verifier="skipped"` para `notify_toast`. Es una acción fire-and-forget donde no podemos readback visual.

**B4 — Sin progress reporting en misiones compuestas**
- Archivo: `Carter_v3/src/carter_v3/agent.py`
- Sección: loop `for i, step in enumerate(steps[:self.step_budget])`
- Problema: El usuario ve silencio hasta que termina la misión. Viola Valor 17.
- Fix: Emitir un hint de progreso que llegue al caller. Puede ser vía `trace.emit("progress", "step", step=i+1, total=len(steps), tool=step.tool_call.name)`. Si el CLI puede mostrar progreso, genial. Si no, al menos documentar el mecanismo.

**B5 — System prompt promueve ejecución cuando usuario solo pregunta capacidad**
- Archivo: `Carter_v3/src/carter_v3/turn_support.py`
- Función: `build_messages()`
- Línea: `"If a safe listed tool clearly fits the current turn, call it now instead of asking whether to continue."`
- Problema: Si el usuario pregunta "¿puedes mutear?", el LLM puede ejecutar `system_mute` directamente.
- Fix: Matizar: `"If the user is clearly requesting an action (imperative mode) and a safe listed tool fits, call it. If the user is asking whether you can do something (capacity question), answer honestly without executing."`

**B6 — Dead code en response_composer.py**
- Archivo: `Carter_v3/src/carter_v3/response_composer.py`
- Líneas: 145-146 — segundo `return` después de primer `return f"Captura guardada..."`
- Fix: Eliminar el `return` inalcanzable.

---

## GAPS DE EXPERIENCIA (Implementar después de bloqueadores)

**G1 — Ampliar parse de local_reminders**
- Archivo: `Carter_v3/src/carter_v3/tools/local_reminders.py`
- Función: `_parse_clock_text()`
- Agregar soporte para:
  - "pasado mañana" (now + 2 días)
  - "el lunes/martes/..." (próximo día de esa semana)
  - "en un rato" (≈30 minutos por defecto)
  - "esta tarde" (hoy a las 18:00 si ahora es < 18:00)
  - "esta noche" (hoy a las 21:00)
- NO hardcodear nombres de días en ningún idioma como routing semántico. Usar `re.search` estructural.

**G2 — Capturar regresiones reales del usuario**
- Archivo: `Carter_v3/tests/test_live_regressions_from_user_log.py`
- Agregar al menos 5 casos de bugs reales (pedir al usuario qué fallos ha experimentado)
- Cada caso debe tener: prompt real, comportamiento incorrecto observado, comportamiento esperado

**G3 — Validación live de C07 (apps) con modelo real**
- Documento a crear: `Carter_v3/LIVE_VALIDATION_C07.md`
- Ejecutar manualmente: abrir Notepad → verificar proceso → cerrar → verificar ausencia
- Registrar: modelo usado, latencia, mission_status, verifier_status
- Esto no es código — es evidencia manual

**G4 — Validación live de C08 (web) con modelo real**
- Similar a G3 pero para web_open_url con https://example.com

---

## INSTRUCCIONES ANTI-HARDCODE (OBLIGATORIAS)

**NUNCA** agregues al runtime:
- `if "steam" in user_text:` — o cualquier marca
- `if "mutea" in user_text:` — o cualquier acción en cualquier idioma
- `if model_name == "qwen":` — o cualquier modelo
- Listas de verbos de acción por idioma
- Listas de apps especiales
- Listas de URLs de ejemplo
- Regex con nombres de apps en el patrón
- Respuestas canned hardcodeadas ("Hola, ¿qué necesitas?")

**SÍ está permitido:**
- Regex estructurales (patrones morfológicos de idioma, no vocabulario semántico)
- Listas en archivos ALLOWLISTED: `secret_filter.py`, `declarative_detector.py`, `guards.py` (solo `_DONE_ANCHORS`)
- Agregar a `_DONE_ANCHORS` solo palabras que son afirmaciones de completitud multi-idioma y que han sido auditadas
- Agregar a `_DANGEROUS_PATTERNS` en policy.py solo patrones de comandos destructivos (no vocabulario semántico)

---

## INSTRUCCIONES ANTI-FAKE-SUCCESS (OBLIGATORIAS)

Antes de cualquier reply que afirme que algo fue hecho:
1. El tool debe haber sido ejecutado (`executed_calls` no vacío)
2. El verifier debe haber retornado `CONFIRMED` o `SKIPPED` (para read-only)
3. El `fake_success_guard` debe haberse evaluado con `any_confirmed=True`
4. El `mission_status` debe ser `COMPLETE` o `PARTIAL_WITH_NEXT_STEP` — nunca `UNVERIFIED` con reply de "completado"

**Frase prohibida sin evidencia:** "listo", "hecho", "ya está", "completado", "done", "all set" — cualquier variante

Si una tool falla o no se verifica, Carter debe decir la verdad:
- "Intenté X, pero no pude verificar el resultado."
- "Lo intenté, pero el proceso no apareció."
- "La notificación fue enviada, pero no puedo confirmar si apareció."

---

## COMANDOS DE VALIDACIÓN (EJECUTAR EN ORDEN)

```bash
# Desde Carter_v3/
cd Carter_v3

# 1. Hardcode guard — debe ser clean
python audit/hardcode_guard.py
# Esperado: "hardcode_guard: clean (N files scanned)"

# 2. Suite completa de tests — debe pasar todos
python -m pytest --tb=short -q
# Esperado: "N passed in X.Xs"

# 3. Test específico de semantic hardcodes
python -m pytest tests/test_no_semantic_hardcodes.py -v
# Esperado: todos PASSED

# 4. Test específico de LLM-first
python -m pytest tests/test_llm_first_responses.py -v
# Esperado: todos PASSED

# 5. Test de guards
python -m pytest tests/test_guards.py -v
# Esperado: todos PASSED

# 6. Test de seguridad
python -m pytest tests/test_security.py -v
# Esperado: todos PASSED

# 7. Tests de runtime no fake success
python -m pytest tests/test_runtime_no_fake_success_live_cases.py -v
# Esperado: todos PASSED

# 8. Runner de minimum testing (si Ollama disponible)
python audit/minimum_testing_runner.py --mode live-safe
# Esperado: 36/36 PASS o similar

# 9. Runner full matrix live-safe-all (si Ollama disponible)
python audit/full_matrix_runner.py --mode live-safe-all
# Esperado: 540/540 PASS
```

---

## CRITERIOS DE READY (TODOS DEBEN CUMPLIRSE)

Para que Carter v3 sea declarado READY pre-voz/pre-cámara, deben cumplirse TODOS:

| # | Criterio | Verificación |
|---|---|---|
| 1 | `python -m pytest` — 0 fallos | Ejecutar y mostrar resultado |
| 2 | `python audit/hardcode_guard.py` — clean | "clean (N files)" |
| 3 | `test_no_semantic_hardcodes.py` — todos PASSED | -v |
| 4 | `test_llm_first_responses.py` — todos PASSED | -v |
| 5 | Confirmación follow-up "Sí"/"OK" funciona | Test en test_pending_intent_followups.py |
| 6 | `fake_success_guard` no pasa claims mid-text | Agregar test en test_guards.py |
| 7 | `notify_toast` verifier cambiado a `skipped` | Verificar en catalog.py |
| 8 | Dead code en response_composer.py eliminado | Líneas 145-146 |
| 9 | System prompt matizado para capacidad vs. ejecución | Verificar con test explícito |
| 10 | Minimum runner 36/36 con modelo real | Si Ollama disponible |
| 11 | Full matrix 540/540 en live-safe-all | Si Ollama disponible |
| 12 | Spotcheck manual C07 documentado (Notepad open/close) | Documento con evidencia |
| 13 | Spotcheck manual C08 documentado (web URL) | Documento con evidencia |
| 14 | Working tree commiteado con todos los cambios | `git status` clean |
| 15 | Nuevo tag aplicado al commit final | `git tag carter-v3-pre-voice-ready` |

---

## ALCANCE — QUÉ NO HACER

**FUERA DE SCOPE — No implementar todavía:**
- Voz / STT / TTS
- Wake word / hotword
- Cámara física
- Visión por cámara
- Transcripción por micrófono
- UI/HUD futurista
- Integración con servicios cloud nuevos
- Nuevas herramientas más allá del catálogo de 32

**NO hacer aunque parezca buena idea:**
- Agregar keywords de idioma como routing semántico
- Crear respuestas canned para acelerar tests
- Simular tool results para pasar tests
- Declarar READY solo porque `pytest` pasa — los tests con ScriptedAdapter no prueban el LLM real
- Crear mocks del LLM como "validación final" — los mocks no son evidencia de comportamiento real

---

## PASOS DE IMPLEMENTACIÓN RECOMENDADOS

### Paso 1: Commit del working tree actual
```bash
git add Carter_v3/src/carter_v3/agent.py
git add Carter_v3/src/carter_v3/guards.py
git add Carter_v3/src/carter_v3/response_composer.py
git add Carter_v3/src/carter_v3/session_state.py
git add Carter_v3/src/carter_v3/tools/local_reminders.py
git add Carter_v3/tests/test_local_reminders.py
git add Carter_v3/tests/test_runtime_no_fake_success_live_cases.py
git commit -m "Checkpoint: pre-audit working tree state"
```

### Paso 2: Fix B1 — Confirmación follow-up
En `session_state.py:_short_same_language_nonsecret()`:
- Agregar excepción explícita para tokens cortos que son afirmativos conocidos
- "sí", "si", "ok", "yes", "dale", "no" — para estos, omitir la verificación de mayúsculas
- Agregar test en `test_pending_intent_followups.py` que verifique "Sí" activa pending_intent

### Paso 3: Fix B2 — fake_success_guard mid-text
En `guards.py:fake_success_guard()`:
- Agregar check de `anchor` en posición final de oración (". {anchor}" o " {anchor}.")
- Limitar a contextos de afirmación, no en citas o frases como "dijo que estaba listo"
- Agregar test en `test_guards.py` para claim en medio de texto

### Paso 4: Fix B3 — notify_toast verifier
En `tools/catalog.py`:
- Cambiar `ToolSpec("notify_toast", ..., verifier="synchronous_ok")` a `verifier="skipped"`
- Verificar que `response_composer.py` no trata toast como CONFIRMED para reportar éxito
- Agregar test que verifique que notify_toast retorna SKIPPED y reply no dice "CONFIRMED"

### Paso 5: Fix B5 — System prompt capacidad vs. ejecución  
En `turn_support.py:build_messages()`:
- Matizar el action_line para distinguir preguntas de capacidad vs. órdenes de ejecución
- Agregar test que verifique "¿puedes mutear?" no ejecuta system_mute

### Paso 6: Fix B6 — Dead code
En `response_composer.py:145-146`:
- Eliminar el segundo `return` inalcanzable

### Paso 7: G1 — Ampliar parse de reminders
En `local_reminders.py:_parse_clock_text()`:
- Agregar soporte para "pasado mañana", "esta tarde", "esta noche"
- Agregar soporte para días de semana (regex estructural, no lista de nombres hardcodeada)
- Agregar tests en `test_local_reminders.py`

### Paso 8: Ejecutar suite completa de validación
```bash
python audit/hardcode_guard.py
python -m pytest --tb=short -q
```
Ambos deben pasar limpiamente.

### Paso 9: Spotcheck manual
- Ejecutar CLAUDE_MANUAL_SPOTCHECK_SET.md con modelo real
- Documentar resultados en LIVE_VALIDATION_SPOTCHECK.md

### Paso 10: Commit y tag final
```bash
git add -A
git commit -m "Close Carter v3 pre-voice/pre-camera blockers"
git tag carter-v3-pre-voice-ready
```

---

## NOTA FINAL PARA CODEX

Este proyecto tiene valores fuertes de honestidad y verificabilidad. La trampa más fácil es "hacer pasar los tests" sin arreglar el problema real. No caigas en esa trampa.

Si encuentras que algo no se puede implementar limpiamente sin violar ContextoCarter.md (sin hardcodes, sin fake success, sin hacks por marca), **dilo honestamente** en lugar de buscar un workaround que pase los tests.

Carter es bueno en la medida en que es confiable. Y es confiable en la medida en que es honesto. Ese es el estándar.
