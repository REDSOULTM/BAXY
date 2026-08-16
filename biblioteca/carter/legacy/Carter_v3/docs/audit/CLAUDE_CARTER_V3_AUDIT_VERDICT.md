# CLAUDE_CARTER_V3_AUDIT_VERDICT.md
# Veredicto Global — Carter v3 Pre-Voz/Pre-Cámara
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# FUENTE: Auditoría completa de código, tests, guía oficial y ContextoCarter.md

---

## VEREDICTO OFICIAL

# ⚠️ CARTER_V3_TESTS_PASS_BUT_RUNTIME_WEAK

---

## Justificación del veredicto

Carter v3 tiene una arquitectura sólida y principios correctos. Los 490 tests unitarios y de integración pasan limpiamente. El hardcode_guard está clean. Las guardas funcionan. La política de seguridad es robusta.

**PERO:**

Los 490 tests usan `ScriptedAdapter` — un adapter que no ejercita ningún modelo LLM real. Lo que se prueba es que el *harness* procesa correctamente los tool calls *si el LLM los genera bien*. No se prueba que el LLM real generará esos tool calls correctamente.

El 540/540 de la matriz oficial en modo `live-safe-all` bloquea todas las tools con side effects reales (apps, web, filesystem, GUI, terminal). Carter responde honestamente "no ejecuté por modo live-safe-all" y eso cuenta como PASS. Esto es técnicamente correcto, pero significa que **nunca se validó live que Carter abra una app real y la verifique**.

No hay medición de latencia en CI. Los tiempos reales con un modelo Ollama corriendo son desconocidos en el estado actual.

---

## Bloqueadores reales

| # | Bloqueador | Evidencia |
|---|---|---|
| B1 | Working tree no commiteado. Tag `carter-v3-18x30-true-ready` no describe el código actual en disco (+202 líneas diff). | `git diff --stat` |
| B2 | Sin validación live de app_open/close real con modelo LLM corriendo. Solo `live-safe-all` (bloqueado). | CLAUDE_18X30_MATRIX_AUDIT.md |
| B3 | Sin medición de latencia con modelo real en CI. C15 (latencia) es inválida en modo scripted. | CLAUDE_18X30_MATRIX_AUDIT.md |
| B4 | Sin progress reporting durante misiones compuestas — usuario ve silencio hasta que termina. | CLAUDE_RUNTIME_CODE_AUDIT.md:2 |
| B5 | `_short_same_language_nonsecret` rechaza "Sí", "OK", "YES" — rompe follow-ups en C17. | CLAUDE_RUNTIME_CODE_AUDIT.md:10 |
| B6 | C05 (intención vs. acción): system_prompt puede causar ejecución cuando el usuario solo pregunta capacidad. | CLAUDE_RUNTIME_CODE_AUDIT.md:12 |

---

## Riesgos altos

| # | Riesgo | Categorías afectadas |
|---|---|---|
| R1 | `fake_success_guard` solo bloquea inicio de reply. Claims en medio de texto no bloqueados. | C12, C07, C08 |
| R2 | `notify_toast` usa `synchronous_ok` — CONFIRMED sin verificación visual real. | C06 |
| R3 | Sin degradación automática por RAM/VRAM. Carter puede cargar modelos aunque el sistema esté al límite. | C15, C22 (ContextoCarter) |
| R4 | Shutdown en inglés solitario puede no bloquearse (`\breboot\b` no está en patterns). | C11, C12 |
| R5 | Typo en nombre de app puede no resolverse si score < threshold del fuzzy resolver. | C16, C14 |
| R6 | `local_reminders` solo persiste en SQLite local. NO envía notificación del sistema. Si el usuario espera notificación del OS, Carter la decepciona. | C04, Reminders |

---

## Gaps por categoría

| Cat | Estado | Brecha principal |
|---|---|---|
| C01 | MOSTLY_READY | Latencia no medida con modelo real |
| C02 | MOSTLY_READY | Dependiente de calidad del LLM |
| C03 | MOSTLY_READY | Con modelos débiles puede llamar tools incorrectas |
| C04 | MOSTLY_READY | Detector declarativo heurístico |
| C05 | PARTIAL | System prompt puede causar ejecución sin pedirlo |
| C06 | MOSTLY_READY | Routing pre-LLM puede conflictuar con LLM |
| C07 | PARTIAL + BLOCKER | Sin validación live de open/close real |
| C08 | PARTIAL + BLOCKER | Sin validación live de web open real |
| C09 | PARTIAL | Distinción biblioteca/tienda no enforced en runtime |
| C10 | PARTIAL | Sin validación live de write/delete |
| C11 | MOSTLY_READY | Pattern de shutdown en inglés incompleto |
| C12 | MOSTLY_READY | Guard solo cubre inicio de reply |
| C13 | WEAK + BLOCKER | Sin evidencia de gui_click real exitoso |
| C14 | PARTIAL | Sin progress reporting |
| C15 | WEAK | Latencia inválida en scripted |
| C16 | MOSTLY_READY | Typo threshold puede fallar |
| C17 | MOSTLY_READY | Confirmación con "Sí"/"OK" rota |
| C18 | PARTIAL | Pocas regresiones reales capturadas |

---

## Tests que SÍ son confiables

| Test | Por qué confiable |
|---|---|
| `test_guards.py` | Prueba guards en aislamiento, sin LLM, determinista |
| `test_security.py` | Prueba PolicyEngine en aislamiento, 29 casos |
| `test_no_semantic_hardcodes.py` | Prueba ausencia de hardcodes en árbol real |
| `test_memory.py` | Prueba SQLite store en aislamiento |
| `test_contracts.py` | Prueba tipos y compute_mission_status |
| `hardcode_guard.py` | AST scan real del código fuente |
| `test_local_reminders.py` | Prueba SQLite de reminders en aislamiento |
| `test_request_patterns_routing.py` | Prueba clasificadores estructurales |

---

## Tests que NO son confiables para "Carter funciona con LLM real"

| Test | Por qué no confiable |
|---|---|
| `test_agent_integration.py` | Usa ScriptedAdapter — no ejercita LLM |
| `test_runtime_persona_and_capabilities.py` | Usa ScriptedAdapter |
| `test_runtime_no_fake_success_live_cases.py` | Usa ScriptedAdapter |
| `test_pending_intent_followups.py` | Usa ScriptedAdapter |
| `full_matrix_runner.py` en modo `scripted` | No hay LLM, no hay latencia real |
| `full_matrix_runner.py` en modo `live-safe-all` | Side effects bloqueados — no prueba acción real |

---

## Reportes previos que SÍ sirven

| Reporte | Valor |
|---|---|
| `CARTER_V3_18X30_TRUE_READY_REPORT.md` | Documenta qué categorías pasaron y en qué modo |
| `FULL_18X30_DIFF_AUDIT.md` | Identifica diferencias entre runs |
| Runs JSON en `audit/runs/` | Evidencia de qué pasó en cada run |
| `test_guards.py` passing | Confirma guards funcionan |
| `hardcode_guard clean` | Confirma ausencia de hardcodes |

## Reportes previos que NO sirven como evidencia de READY completo

| Reporte | Por qué no sirve solo |
|---|---|
| `CARTER_V3_18X30_TRUE_READY_REPORT.md` | 540/540 en `live-safe-all` no prueba acción real |
| Tags `carter-v3-18x30-true-ready` | Working tree tiene +202 líneas no commiteadas |
| `TRUE_CARTER_V3_TEXT_CORE_READY_REPORT.md` | Basado en runs con ScriptedAdapter mayormente |
| `TEST_TRUE_READY_REPORT.md` | Mismo problema |

---

## Qué NO se debe tocar hasta que Codex termine

1. La arquitectura base del engine (AgentEngine, ToolDispatcher, VerificationManager)
2. Los guards existentes — son correctos
3. La política de seguridad — es sólida
4. El catálogo de herramientas — 32 tools es el límite documentado
5. El sistema de memoria SQLite — funciona correctamente
6. El schema de local_reminders — funciona

---

## Qué debe hacer Codex

### Urgente (Bloqueadores)

1. **Commitear working tree** — los +202 líneas no commiteadas deben estar en un commit antes de continuar
2. **Fix confirmación follow-up** — `_short_same_language_nonsecret` debe aceptar "Sí", "SI", "OK", "YES"
3. **Fix fake_success_guard para mid-text claims** — extender detección más allá del inicio de reply
4. **Fix notify_toast verifier** — cambiar de `synchronous_ok` a `skipped` (honesto: no podemos verificar que la notificación apareció visualmente)
5. **Fix system_prompt** — matizar "call it now" para que no ejecute cuando el usuario solo pregunta capacidad

### Importante (Gaps de experiencia)

6. **Agregar progress reporting** en misiones compuestas — "Ejecutando paso 1/3: ..."
7. **Validar live open/close Notepad** con modelo real y documentar como evidencia oficial
8. **Validar live web_open_url** con ejemplo.com y documentar
9. **Ampliar local_reminders parse** — "pasado mañana", días de semana, "mañana a las X"
10. **Capturar 5+ regresiones reales** del usuario en test_live_regressions_from_user_log.py

### Validación (Antes de declarar READY final)

11. Correr `python -m pytest` — debe pasar 0 fallos
12. Correr `python audit/hardcode_guard.py` — debe ser clean
13. Correr spotcheck manual del CLAUDE_MANUAL_SPOTCHECK_SET.md con modelo real
14. Medir latencia real de inputs triviales (< 8s) con el modelo configurado
15. Correr `full_matrix_runner.py` en modo `live-safe-all` — debe ser 540/540
16. Documentar resultado en un reporte nuevo con fecha 2026-05-06

---

## Declaración final

Carter v3 no está al 100% pre-voz/pre-cámara. Está aproximadamente al **75-80%** del núcleo texto. La arquitectura es correcta, los principios son sólidos, y muchas categorías funcionan bien. Pero hay bloqueadores reales que deben resolverse antes de que sea honesto declarar READY y comenzar voz/cámara.

**El principal riesgo no es que Carter sea deshonesto o inseguro — esos sistemas funcionan bien. El principal riesgo es que nunca se ha validado live que Carter puede abrir apps reales, verificarlas, y manejar follow-ups con un modelo LLM real corriendo en condiciones normales.**

Voz y cámara deben esperar hasta que Codex cierre los bloqueadores y se ejecute el spotcheck manual completo.
