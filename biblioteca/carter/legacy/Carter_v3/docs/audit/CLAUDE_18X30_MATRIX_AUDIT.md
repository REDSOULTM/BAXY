# CLAUDE_18X30_MATRIX_AUDIT.md
# Auditoría de la Matriz Oficial 18×30
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## Preguntas de auditoría

### ¿official_matrix_cases.py representa fielmente la guía oficial?

**RESPUESTA: PARCIALMENTE.**

`official_matrix_cases.py` parsea la guía `Carter_v3_GUIA_OFICIAL_TESTING (1).md` mediante regex de encabezados y filas de tabla. El parser extrae prompts, herramientas permitidas, herramientas prohibidas, latencia y política esperada. Es un parser, no una copia manual.

**Problemas encontrados:**
1. El parser usa `_tool_tokens()` para inferir qué herramientas espera cada caso. Esta función tiene MUCHA lógica condicional interna (100+ líneas de `if ... in folded`), lo que significa que la traducción de "tools" en el Markdown a nombres de herramientas Python puede diferir de la intención del guía.
2. El parser incluye `if "steam" in folded_tools: add("app_open", "window_focus", "process_list", "web_search")` — esta es una excepción especial para Steam que existe en el parser de la guía. Aunque no está en el runtime, sí puede afectar qué herramientas se "esperan" para casos C09.
3. `_is_destructive_or_sensitive()` usa tokens en español para clasificar casos peligrosos — esta función tiene keyword tokens mezclados que podrían dar falsos negativos.

### ¿Hay exactamente 18 categorías y 30 casos por categoría?

La guía oficial define 18 categorías (C01-C18). El código asume eso mediante el heading RE `## C{cat:02d}`. Según el runner, hay exactamente 540 casos (`18 × 30`).

**No se puede verificar sin correr el parser**, pero el código está diseñado para parsear la guía tal cual. La guía fue leída y efectivamente tiene las 18 categorías con 30 casos cada una.

### ¿Los validadores son estrictos o permisivos?

**RESPUESTA: MIXTO — ALGUNAS VALIDACIONES SON DÉBILES.**

Del análisis del `full_matrix_runner.py`:

- **Modo `live-safe-all`**: bloquea TODAS las tools con side effects reales antes de dispatch. Esto significa que C07 (apps), C08 (web), C10 (filesystem), C11 (terminal), C13 (GUI) corren con las tools bloqueadas — Carter responde "no ejecuté esa acción en modo live-safe-all". Luego el validator verifica si la respuesta es honesta. **Este modo NO prueba que Carter puede realmente abrir/cerrar apps; prueba que Carter responde honestamente cuando no puede ejecutar.**

- **Validación de mission_status**: el runner verifica `mission_status` pero no el contenido detallado de la respuesta para la mayoría de casos.

- **Validación de NO tool use para casos conversacionales**: sí existe — verifica `tool_families` == `[]`.

- **Validación de latencia**: verifica que `total_ms < max_total_ms`. Pero `max_total_ms` para casos en modo `scripted` no tiene límite real de latencia (scripted es instant).

### ¿Hay "PASS" por respuesta no vacía?

**SÍ, PARCIALMENTE.** Para algunos casos donde `expected_tool_policy == "none"`, el validador solo comprueba que `mission_status` no sea `FAILED` y que no se llamó ninguna tool. No verifica el contenido de la respuesta.

### ¿Hay peligrosos bloqueados correctamente?

**SÍ.** Los casos C12 (safety) son verificados explícitamente para que la respuesta sea `BLOCKED_BY_POLICY_*` o `NEEDS_USER`. El `PolicyEngine` en `security/policy.py` tiene 20+ patterns.

### ¿Hay casos GUI/screen realmente cubiertos o solo simulados?

**SOLO SIMULADOS en live-safe-all.** En modo `live-safe-all`, `gui_click` y `gui_type` están en `LIVE_SAFE_ALL_SIDE_EFFECT_TOOLS`. Carter no puede hacer click ni type realmente — responde que no puede en ese modo. Los casos C13 en este modo solo prueban que Carter dice honestamente que necesita permiso.

---

## Tabla de Auditoría por Categoría

| Cat | Nombre oficial | Casos guía | Casos runner | Fidelidad | Validación | Live-safe | Riesgo | Veredicto |
|---|---|---:|---:|---|---|---|---|---|
| C01 | Conversación simple & bajo contenido | 30 | 30 | ALTA — casos triviales bien parseados | tool_families=[] + no-blocked | Seguro — sin side effects | BAJO | OFFICIAL_AND_STRICT |
| C02 | Identidad & scope de Carter | 30 | 30 | ALTA — preguntas de identidad sin tools | tool_families=[] + ms≠FAILED | Seguro | BAJO | OFFICIAL_AND_STRICT |
| C03 | Conocimiento sin tools innecesarias | 30 | 30 | ALTA — preguntas generales | tool_families=[] o clock_now | Seguro | BAJO | OFFICIAL_BUT_WEAK_VALIDATION |
| C04 | Memoria, preferencias y olvido | 30 | 30 | ALTA — memory_save/recall/delete | verifica llamada a memory_ tools | Seguro — local DB | BAJO | OFFICIAL_AND_STRICT |
| C05 | Distinción intención vs. acción | 30 | 30 | MEDIA — algunos casos ambiguos | ms + no-wrong-tool | Seguro | MEDIO | OFFICIAL_BUT_WEAK_VALIDATION |
| C06 | Tool routing & contratos | 30 | 30 | ALTA — verifica tool_family correcta | tool_family exacto verificado | Seguro — clock, volume read | BAJO | OFFICIAL_AND_STRICT |
| C07 | Apps, ventanas, procesos | 30 | 30 | MEDIA — en live-safe-all se bloquean | Carter dice "no ejecuté" | BLOQUEADO en live-safe-all | ALTO | OFFICIAL_BUT_WEAK_VALIDATION |
| C08 | Web, URLs, browser | 30 | 30 | MEDIA — web_open bloqueado | Carter dice "no ejecuté" | BLOQUEADO en live-safe-all | ALTO | OFFICIAL_BUT_WEAK_VALIDATION |
| C09 | Steam biblioteca vs. tienda | 30 | 30 | MEDIA — parser tiene hack de steam | Verificación de NO steam_run | Parcialmente | MEDIO | PARTIALLY_REINTERPRETED |
| C10 | Filesystem operations | 30 | 30 | ALTA — delete/write bloqueados | Honestidad del reply | BLOQUEADO (write/delete) | MEDIO | OFFICIAL_BUT_WEAK_VALIDATION |
| C11 | Terminal & policy | 30 | 30 | ALTA — terminal bloqueado | ms=BLOCKED o NEEDS_USER | BLOQUEADO en live-safe-all | MEDIO | OFFICIAL_AND_STRICT |
| C12 | Safety & fake success | 30 | 30 | ALTA — casos peligrosos críticos | ms=BLOCKED obligatorio | Seguro — solo verifica bloqueo | BAJO | OFFICIAL_AND_STRICT |
| C13 | GUI/visión con re-observación | 30 | 30 | BAJA — gui_click/type bloqueados | Carter dice "no ejecuté" | BLOQUEADO en live-safe-all | MUY ALTO | OFFICIAL_BUT_WEAK_VALIDATION |
| C14 | Misiones compuestas | 30 | 30 | MEDIA — compound intent verificado | ms≠FAILED, partial OK | Parcial | ALTO | PARTIALLY_REINTERPRETED |
| C15 | Latencia & recursos | 30 | 30 | BAJA — latencia en scripted = 0ms | Solo ms + total_ms < max | En scripted no hay latencia real | ALTO | NEEDS_REAL_CASES |
| C16 | Multilingüe, typos, informalidad | 30 | 30 | ALTA — variedad de inputs | ms≠FAILED + no-wrong-script | Seguro | BAJO | OFFICIAL_AND_STRICT |
| C17 | Follow-ups & limpieza de contexto | 30 | 30 | ALTA — pending intent verificado | Verifica context carry-over | Seguro — sin side effects | BAJO | OFFICIAL_AND_STRICT |
| C18 | Regresiones reales del usuario | 30 | 30 | MEDIA — algunos sintéticos, no todos reales | ms + no-canned-reply | Seguro | MEDIO | PARTIALLY_REINTERPRETED |

---

## Hallazgos críticos de la matriz

### Hallazgo 1: live-safe-all bloquea categories enteras de acción real

**C07, C08, C10, C11, C13** corren con side effects bloqueados. El resultado es que Carter responde "no ejecuté porque estoy en modo live-safe-all". Eso es una respuesta **honesta**, y el validador la acepta como PASS. Pero **NO es evidencia de que Carter puede realmente abrir apps, navegar web, o hacer click**. Es evidencia de que Carter responde honestamente cuando no puede.

Para tener 540/540 con estas categorías, necesitarías un modo `live` real con rollback. Ese modo existe en el runner pero genera riesgo real para el PC.

### Hallazgo 2: C15 (Latencia) es inválido en modo scripted

La categoría de latencia solo tiene validez con un modelo LLM real corriendo. En modo scripted, `total_ms ≈ 0`. Reportar 30/30 PASS en C15 en modo scripted no dice nada sobre latencia real.

### Hallazgo 3: C09 (Steam) tiene hack en el parser

`_tool_tokens()` tiene `if "steam" in folded_tools: add("app_open", "window_focus", "process_list", "web_search")`. Esto es un hack en el parser para manejar el caso especial de Steam en la guía. El runtime no tiene este hack (limpio), pero el parser de la guía sí. Esto puede causar que los casos C09 "esperen" más herramientas de las que el runtime realmente necesita, y que el validador sea más permisivo con C09.

### Hallazgo 4: Validación de contenido débil para C03, C05

Para categorías conversacionales (C03, C05), el validador verifica `mission_status` y `tool_families` pero no el **contenido real de la respuesta**. Carter podría responder cualquier cosa siempre que no llame tools y no reporté `FAILED`. La calidad de la respuesta conversacional no está medida automáticamente.

### Hallazgo 5: C18 mezcla regresiones reales con sintéticas

La categoría C18 debería capturar bugs reales del usuario. Pero el código de `test_live_regressions_from_user_log.py` tiene solo unos pocos casos y algunos son sintéticos. La guía pide que cada bug real se convierta en caso permanente. Eso no está completamente implementado.

---

## ¿Es confiable el 540/540?

**VEREDICTO: CONFIABLE PARA LO QUE MIDE, PERO NO PRUEBA TODO LO QUE PARECE.**

El 540/540 demuestra:
- ✅ Carter no llama tools cuando no debe (C01-C03, C05, C16-C17)
- ✅ Carter bloquea acciones peligrosas (C11, C12)
- ✅ Carter maneja memoria correctamente (C04, C06)
- ✅ Carter responde honestamente cuando está bloqueado por live-safe-all (C07, C08, C10, C13)
- ✅ Carter detecta compound intent (C14, C17)

El 540/540 NO demuestra:
- ❌ Carter puede realmente abrir/cerrar apps y verificarlo (necesita `live` mode real)
- ❌ Carter tiene latencia aceptable con modelos reales (C15 es inválido en scripted)
- ❌ Carter puede hacer click en GUI y verificar resultado (bloqueado en live-safe-all)
- ❌ Carter navega web y verifica la pestaña abierta
- ❌ Calidad de respuesta conversacional (solo se verifica que no falla)
