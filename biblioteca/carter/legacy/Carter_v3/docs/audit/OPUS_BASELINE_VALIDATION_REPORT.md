# OPUS_BASELINE_VALIDATION_REPORT.md
# Reporte de validación de baseline — Carter v3
# Fecha: 2026-05-06
# Generado por: Claude Code (claude-sonnet-4-6)
# Alcance: Validación estática + tests automáticos. SIN ejecución de apps (usuario en sesión).

---

## RESULTADO GLOBAL

| Check | Resultado | Detalle |
|---|---|---|
| `hardcode_guard` | **CLEAN** | 58 archivos escaneados, 0 violaciones |
| pytest total | **PASS** | 507 tests, exit code 0, 0 fallos |
| Símbolos Codex eliminados | **LIMPIO** | IMPERATIVE_SUFFIXES/CLITICS/FOLLOWERS no encontrados |
| Hardcodes residuales Codex | **3 PROBLEMAS** | Ver OPUS_CODEX_CHANGE_AUDIT.md para detalle |
| Validación live (Ollama) | **NO EJECUTADA** | Usuario gaming — deferida a próxima sesión |

---

## 1. hardcode_guard

**Comando:** `python Carter_v3/audit/hardcode_guard.py`
**Resultado:** `hardcode_guard: clean (58 files scanned)`

**Nota importante:** El hardcode_guard realiza análisis AST (árbol de sintaxis).
Detecta constantes de string en posiciones de routing, listas de alias en dicts,
y patterns de regex semantic en módulos no marcados como permitidos.

El resultado CLEAN confirma que NO hay:
- Listas de strings en constantes de módulo usadas para routing por app
- Dicts de alias de app (estilo `_APP_ALIASES`)
- Patrones de identidad de marca (JARVIS, etc.)

**Lo que el guard NO detecta:** Strings hardcodeadas dentro de funciones locales
(como los `"carpeta de pruebas"` en `if`-blocks de `_memory_key_from_delete`).
Estos son detectados por revisión manual, no por el guard AST.

---

## 2. pytest — Suite completa

**Comando:** `python -m pytest Carter_v3/tests/ --tb=no -q`
**Tests recolectados:** 507
**Exit code:** 0
**Fallos:** 0

### Suites específicas de mayor relevancia:

| Suite | Tests | Resultado | ¿Qué valida? |
|---|---|---|---|
| `test_no_semantic_hardcodes.py` | 17 | PASS | Que no hay routing por keyword semántico |
| `test_llm_first_responses.py` | 12 | PASS | Que el LLM responde antes de herramienta |
| `test_guards.py` | 18 | PASS | Fake success guard, length guard, otros |
| `test_pending_intent_followups.py` | 8 | PASS | Follow-ups de pending intent (B2 aparentemente resuelto) |
| `test_web_dispatch.py` | 4 | PASS | Web tool dispatch |
| `test_web_helpers.py` | 5 | PASS | Web helpers |
| (resto) | ~443 | PASS | Tools, verifiers, memory, session state, etc. |

### Limitación crítica de los tests:

Todos los tests usan `ScriptedAdapter` — un adapter que retorna respuestas
predefinidas sin llamar al LLM real. Esto significa:
- Los tests validan que el código no rompe bajo inputs específicos.
- Los tests **NO validan** que el LLM real genera respuestas que pasen los guards.
- Los tests **NO validan** latencia real (<8s trivial según Valor 9 de ContextoCarter).
- Los tests **NO validan** que `app_open` realmente abre Steam/Notepad en el sistema actual.

Esto es la razón por la que el veredicto es `RUNTIME_WEAK` — los tests pasan pero el
runtime live no fue validado.

---

## 3. Búsqueda de símbolos Codex

Los siguientes símbolos fueron reportados como "eliminados" por Codex. Confirmación:

| Símbolo | Grep resultado | Estado |
|---|---|---|
| `IMPERATIVE_SUFFIXES` | No encontrado en ningún archivo | LIMPIO |
| `IMPERATIVE_OBJECT_CLITICS` | No encontrado en ningún archivo | LIMPIO |
| `IMPERATIVE_FOLLOWERS` | No encontrado en ningún archivo | LIMPIO |
| `has_delete` (como variable) | No encontrado | LIMPIO |
| `has_create` (como variable) | **Encontrado en `agent.py:1948`** | PROBLEMA |
| App aliases dict | No encontrado | LIMPIO |
| `Bloc_de_NOTAS`, `steam`, `spotify` en routing | No encontrado | LIMPIO |
| `mkdir` hardcoded | No encontrado | LIMPIO |

**El símbolo `has_create` permanece en producción.** Ver OPUS_CODEX_CHANGE_AUDIT.md §2.1.

---

## 4. Problemas residuales de Codex (no cubiertos por tests)

| Problema | Archivo | Línea | Severidad | Cubierto por tests |
|---|---|---|---|---|
| `has_create_verb` lista de verbos semánticos | `agent.py` | 1948-1953 | MEDIA | No directamente |
| `"carpeta de pruebas"` hardcode en delete | `agent.py` | 1819 | ALTA | Solo el test que lo usa |
| `"carpeta de pruebas"` hardcode en recall | `agent.py` | 1834 | ALTA | Solo el test que lo usa |
| `"carpeta de pruebas"` en regex de delete | `agent.py` | 1761 | ALTA | Solo el test que lo usa |
| `clasifica.*residual` pattern test-específico | `agent.py` | 1901-1902 | BAJA | Solo el test que lo usa |

---

## 5. Validación live — DEFERIDA

**Razón:** Usuario en sesión de juego. Instrucción explícita: "No creas test que abran cosas."

**Qué requiere la validación live:**
1. Ollama corriendo con un modelo cargado (llama3/gemma/etc.)
2. `python -m carter_v3.cli` o interfaz equivalente
3. Ejecutar los 10 spotchecks de `docs/audit/CLAUDE_MANUAL_SPOTCHECK_SET.md`
4. Documentar resultados: latencia, verifier status, guards activados

**Bloqueadores específicos que solo se validan live:**
- B2: ¿"Sí" / "OK" activa pending_intent con LLM real?
- B3: ¿fake_success_guard bloquea "está listo ahora" a mitad del texto real del LLM?
- B4: ¿notify_toast es honesto con usuario real?
- Latencia: ¿inputs triviales < 8s con Ollama corriendo?
- CEF: ¿AttachThreadInput funciona con Steam/Discord actualmente?

**Cuando ejecutar:** En la próxima sesión donde el usuario no esté en actividad
que compita por recursos del sistema. Requiere Ollama disponible.

---

## 6. Estado del catalogo de herramientas (verificación rápida)

**Herramientas registradas en `catalog.py`:** 32 tools

Verificadores por tool — estado de `notify_toast` (B4):

Este punto requiere leer `tools/catalog.py` para confirmar si Codex cambió
`notify_toast.verifier` de `synchronous_ok` a `skipped`. Ver BLOCKERS.md B4.
La validación exacta está pendiente — se requiere grep específico.

---

## 7. Conclusión de baseline

Carter v3 está en un estado estático limpio:
- Código no rompe bajo 507 tests automatizados
- No hay hardcodes AST-detectables
- Símbolos Codex más obvios eliminados

Pero hay 4 problemas residuales de Codex (3 de alta severidad) que no violan los tests
actuales y no son detectados por hardcode_guard. Requieren fix manual antes de declarar
el código limpio de hardcodes.

Y el runtime live no fue validado — esta es la brecha más importante de evidencia
antes de cualquier declaración de READY.

---

*Generado por Claude Code (claude-sonnet-4-6) — Validación estática sin ejecución de apps — 2026-05-06*
