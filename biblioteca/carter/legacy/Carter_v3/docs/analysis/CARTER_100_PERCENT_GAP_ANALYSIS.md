# CARTER_100_PERCENT_GAP_ANALYSIS.md
# Análisis de Brechas para Que Carter Sea el 100%
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## 1. ¿Qué le falta a Carter para ser mejor que Mark?

Carter ya es mejor que Mark en los aspectos más importantes (privacidad, verifier, policy, seguridad, hardcodes, tests, CEF app control). Pero le falta:

- **Progress reporting durante misiones** — Mark muestra estados claros, Carter está en silencio
- **Browser automation real** — Mark tiene Playwright con tabs y forms; Carter solo abre URLs
- **Validación live confirmada** — Mark "funciona" en producción (aunque con fake success). Carter no ha sido validado con LLM real en runtime
- **UX de primera ejecución** — Mark tiene overlay de setup; Carter requiere editar configs manualmente

## 2. ¿Qué le falta para ser mejor que OpenClaw?

- **Browser Playwright** — OpenClaw tiene browser automation real con sandbox Docker; Carter no
- **Context compaction** — Carter trunca contexto sin avisar; OpenClaw lo maneja gracefully
- **PTY terminal** — Carter no soporta comandos interactivos; OpenClaw sí
- **Semantic memory recall** — Carter busca por key exacto; OpenClaw tiene embeddings
- **Model failover** — Carter depende de que Ollama esté disponible; OpenClaw rota entre providers
- **Test coverage con LLM real** — Carter tiene 490 tests scripted; OpenClaw tiene E2E tests

## 3. ¿Qué le falta para ser mejor que Open Interpreter/OpenHands/etc.?

- **Streaming de output** — Open Interpreter hace streaming de la ejecución en tiempo real; Carter no
- **Task visibility** — OpenHands tiene task state visible; Carter no
- **State machine explícita** — LangGraph tiene grafos verificables; Carter tiene imperative code
- **Browser real** — OpenHands tiene Playwright; Carter no
- **Live tests** — Mayoría tienen al menos tests de integración con LLM; Carter no

## 4. ¿Qué capacidades debe tener ANTES de voz/cámara?

### Bloqueadores absolutos (sin estos, voz/cámara no tiene sentido):
- **B2 fixed**: Confirmaciones follow-up funcionando ("Sí"/"OK"/"YES")
- **B3 fixed**: fake_success_guard cubre mid-text
- **B4 fixed**: notify_toast honesto (SKIPPED)
- **B5 fixed**: Progress reporting en misiones compuestas
- **B6 fixed**: System prompt no ejecuta cuando usuario solo pregunta
- **Live validation**: Al menos 5 spotchecks manuales con modelo Ollama real (Notepad, web, terminal, filesystem, memory)
- **Latencia medida**: Tiempos reales documentados para inputs triviales (<8s meta)

### Muy recomendado antes de voz (no bloqueadores absolutos):
- SSRF protection en web_fetch
- Error classification estructural (retry/skip/abort)
- Degradación automática por RAM/VRAM
- Model failover entre adapters
- Context compaction básica

## 5. ¿Qué capacidades pueden esperar?

- Browser Playwright (P1 — importante pero no bloquea voz)
- PTY terminal (P1 — útil pero no bloquea voz)
- Semantic memory via embeddings (P2)
- Docker sandbox (P2)
- Task persistence (P2)
- Webcam snapshot (esperar hasta fase cámara)
- Multi-agent (P3 — fuera de scope)
- Plugin marketplace (P3)

## 6. ¿Qué debe probarse en vivo?

| Test | Herramienta | Criterio |
|---|---|---|
| Abrir Notepad | app_open | Proceso existe post-open, window visible |
| Cerrar Notepad | app_close | Proceso no existe post-close |
| Abrir URL (ejemplo.com) | web_open_url | Ventana browser activa, URL visible |
| Escribir archivo en Desktop | filesystem_write_text | Archivo existe con contenido correcto |
| Ejecutar `echo hello` en terminal | terminal_run_command | exit_code=0, output correcto |
| Guardar memoria "Me llamo X" | memory_save | Dato en SQLite, retrievable |
| Recall "cómo me llamo" | memory_recall | Retorna dato guardado |
| Crear reminder "mañana a las 9" | local_reminder_create | Registro en SQLite |
| Seguimiento "Sí" confirmando acción previa | pending_intent | Acción ejecutada sin nuevo LLM call |
| Input trivial "hola" | (sin tools) | Respuesta <8s, sin tools activadas |
| Input trivial "a" | (sin tools) | Respuesta rápida, sin GUI, sin ventana activa |
| Misión compuesta "abre X y ciérrala" | compound | Dos steps con verificación y progreso visible |

## 7. ¿Qué tests actuales son insuficientes?

| Test | Por qué insuficiente |
|---|---|
| `test_agent_integration.py` (ScriptedAdapter) | No ejercita LLM real; no valida que el modelo generará el tool call correcto |
| `test_runtime_no_fake_success_live_cases.py` (ScriptedAdapter) | No prueba que el LLM real no inventará éxitos |
| `test_pending_intent_followups.py` (ScriptedAdapter) | No prueba el bug B2 con LLM real generando "Sí" como respuesta |
| `full_matrix_runner.py` modo `live-safe-all` | Bloquea todas las tools con side effects; no prueba acción real |
| C15 (latencia) en modo scripted | Sin LLM real, no hay latencia medible |
| `test_llm_first_responses.py` (ScriptedAdapter) | No prueba que el LLM real responde conversacionalmente sin tools |

## 8. ¿Qué validadores son débiles?

| Validador | Debilidad |
|---|---|
| `notify_toast` verifier (synchronous_ok) | Reporta CONFIRMED sin verificación visual → B4 |
| `fake_success_guard` | Solo cubre inicio de reply → B3 |
| `_short_same_language_nonsecret` | Rechaza "Sí"/"OK"/"YES" → B2 |
| `terminal` verifier sin exit_code | Si el dispatcher no incluye exit_code → UNVERIFIABLE en vez de CONFIRMED |
| `system_mute` verifier | Ningún verifier real para mute (solo volumen) |
| Latencia en CI | Sin LLM real, la latencia es siempre ~0ms |

## 9. ¿Qué partes del código están demasiado complejas?

| Parte | Problema |
|---|---|
| `agent.py` (1100 líneas) | Fallback chains como if-chains profundas. Difícil agregar nueva lógica sin romper algo. |
| `turn_support.py:build_messages` | Concatenación de strings para system prompt. Si un bloque falla silenciosamente, el prompt está incompleto. |
| `session_state.py:_short_same_language_nonsecret` | Condición multi-parte difícil de razonar sobre edge cases. |
| `verifier.py:_app_open` | Lógica de causal baseline es correcta pero compleja. Difícil de testear sin proceso real. |
| `request_patterns.py:synthesise_structural_tool_calls` | Orden de 11 patterns con primer match wins. Agregar un nuevo pattern requiere entender todos los anteriores. |

## 10. ¿Qué partes deben congelarse porque ya están bien?

| Parte | Por qué congelar |
|---|---|
| `contracts.py` | Tipos y estados son correctos. compute_mission_status es sólido. No tocar. |
| `security/policy.py` | 20+ patterns, bilingüe, arguments re-scan. Agregar solo si hay gap específico documentado. |
| `tools/catalog.py` (32 tools, assert ≤32) | El límite es correcto. No agregar tools sin razón fuerte. |
| `memory/store.py` | SQLite con secret filter y dedup está correcto. |
| `adapters/tool_call_parser.py` | 4 formatos robustos. Estable. |
| `perception/ladder.py` | Cheapest viable perception es correcto. |
| `models/selector.py` | Zero if-model-name. Correcto. |
| `resolvers/resource_resolver.py` | Fuzzy matching sin hardcodes. Correcto. |

---

## Tabla de gaps consolidada

| Gap | Severidad | Competidor que lo hace mejor | Evidencia | Fix recomendado | Dificultad | Prioridad |
|---|---|---|---|---|---|---|
| Confirmaciones "Sí"/"OK"/"YES" rotas | ALTA | Todos | CLAUDE_RUNTIME_CODE_AUDIT.md:10 | Fix `_short_same_language_nonsecret` | BAJA | P0 |
| fake_success mid-text no bloqueado | ALTA | Carter mismo (el design) | CLAUDE_RUNTIME_CODE_AUDIT.md:4 | Extender guard a texto completo | MEDIA | P0 |
| notify_toast CONFIRMED sin evidencia | MEDIA | Carter mismo | CLAUDE_RUNTIME_CODE_AUDIT.md:7 | Cambiar a SKIPPED | BAJA | P0 |
| System prompt ejecuta en vez de explicar | MEDIA | Carter mismo | CLAUDE_RUNTIME_CODE_AUDIT.md:12 | Matizar cláusula | BAJA | P0 |
| Sin progress en misiones compuestas | ALTA | Mark XXXIX, OpenClaw | ContextoCarter Valor 17 | Emit progreso en loop de steps | BAJA | P0 |
| Sin validación live con LLM real | CRÍTICA | Todos | CLAUDE_CARTER_V3_AUDIT_VERDICT.md | Spotcheck manual urgente | BAJA (proceso) | P0 |
| Sin browser automation | ALTA | Mark, OpenClaw, OpenHands | CARTER_VS_COMPETITION_MATRIX.md dim 9 | Agregar Playwright tool | MEDIA | P1 |
| Sin SSRF protection | MEDIA | OpenClaw | OpenClaw audit | Validar IPs en web_fetch | BAJA | P1 |
| Sin context compaction | MEDIA | OpenClaw | Turns cap hardcodeado en 6 | Summarize cuando overflow | MEDIA | P1 |
| Sin PTY terminal | BAJA | OpenClaw, Open Interpreter | Comparativa dim 11 | pty module o pexpect | ALTA (Windows PTY) | P1 |
| Sin model failover | MEDIA | OpenClaw | Carter depende de Ollama siempre | Adapter priority list | BAJA | P1 |
| Memory sin categorías | BAJA | Mark XXXIX | Comparativa dim 7 | Agregar campo category | BAJA | P1 |
| Sin degradación RAM/VRAM | MEDIA | ContextoCarter Valor 22 | Audit verdict R3 | VRAM check en startup | BAJA | P1 |
| Memory sin recall semántico | BAJA | OpenClaw | Comparativa dim 6 | Embeddings locales | ALTA | P2 |
| agent.py monolito 1100 líneas | MEDIA | OpenClaw | Análisis interno | Refactorizar fallback chains | MEDIA | P2 |
