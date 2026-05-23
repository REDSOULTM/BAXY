# NIGHT AUDIT — 2026-05-16 (sesión nocturna 9h)

Branch: `PortandoLoMejor`
Baseline commit: `e70c09b fix(streaming): Disney+ y Max URLs reales + GUI search shortcut`
Baseline tests (pytest): **440 passed, 0 failed** (unittest discover muestra 228; pytest collecta 440 — pytest es la source of truth).

WIP previo guardado en stash `pre-night-audit-WIP-2026-05-16` (test_gx_features.py, voice/stt.py, voice/app_inventory.py — sin tocar durante esta sesión).

---

## Plan
- Fase 0: Bootstrap ✅
- Fase 1: Trace audit ✅
- Fase 2: P0 crashes
- Fase 3: Tool robustness
- Fase 4: Pending action edge cases
- Fase 5: Router corpus
- Fase 6: Verifiers/guards
- Fase 7: Adjacent subsystems
- Fase 8: DX/perf + reporte final

---

## 23:30 — Phase 0: Bootstrap
- git status limpio tras stash de WIP previo.
- Baseline 440 tests passed (pytest).
- traces.jsonl = 4834 líneas, 1.2 MB.
- 19 archivos de test en `gemma4_agent/`.
- Confirmado plan, arranco Fase 1.

## 23:55 — Phase 1: Trace audit

Script: `scripts/trace_audit.py` (UTF-8, parseo robusto de TZ).
Output completo en `/tmp/trace_audit.md` (no commiteado).

### Findings — clasificados

**P0 — Bugs activos serios**: ninguno. Las fallas históricas (tasklist timeouts 15s, "unsupported media provider" para spotify, footer `[misión:...]` leak en final) están **todas ya parcheadas** en commits posteriores (a27c264 perf tools, b3f2e27 spotify nativo + sin footer, etc.). Confirmado por correlación timestamp del trace vs `git log --since`.

**P1 — LLM context overflow (4× `exceed_context_size_error` 16384 ctx)**:
- Ts: 2026-05-12T15:40 → 15:43 (todos seguidos en ~3min).
- Mensaje: `request (16489 tokens) exceeds the available context size (16384 tokens)`.
- Acción: investigar si hay budget/truncate en `llm_client.py` o `agent.py` y validar con test que pre-trim agresivo cuando se supera límite.

**P1 — Connection forcibly closed (`WinError 10054`)**:
- 2× el 2026-05-15 20:05 y 20:51.
- ¿llm_client retry handles 10054 graceful? Hay `test_llm_client_retry.py` — chequear si cubre este caso.

**P2 — `mission_outcome` ruido**:
- 27 UNVERIFIED de 35 outcomes en últimos 7 días.
- La mayoría son chitchat puro ("No entendí", "Soy Gemma 4...", "Je peux parler français").
- El evaluador emite mission_outcome incluso cuando no hay misión real → ruido en logs + métrica engañosa.
- Mejora: skip mission_outcome cuando `expected_total == 0` y es turno conversacional. Pero requiere confirmar diseño — `[DEFERRED-decision]`.

**P3 — `browser action=minimize` rebota generic**:
- 1 ocurrencia (14 may). LLM intentó pero schema browser no soporta minimize (es de `window`).
- Polish: detectar y sugerir tool correcta en validation error.

**P3 — `download status=failed "missing url"`**:
- 1 caso. Validación tardía. Polish: chequeo de presencia + mensaje claro al inicio del handler.

### Sin acción
- Loops/retry repetido: **0 patrones** detectados (≥3 calls mismos args en un turn).
- `verifier confirmed=False`: 0 eventos (el verifier no emite reject explícito, solo no-confirms vía UNVERIFIED).
- Tools sin uso: 0 críticos.

### Plan Fase 2
1. **P1a** — overflow ctx: agregar truncate de mensajes antiguos en `llm_client.py` (o agente) cuando excede budget. Test que docu el límite.
2. **P1b** — WinError 10054: confirmar retry en cliente. Test sintético que mockea `ConnectionResetError`/10054 y verifica retry.
3. **P2 polish (mission_outcome chitchat)**: skip si turn es 0 tools + sin patrón "imperative". Anota `[DEFERRED-decision]` si requiere cambio de diseño.

## 00:35 — Phase 2 (P0/P1 fixes + tests)

### 2a — context overflow (commit 1912230)
- Investigación: `_looks_like_context_overflow` ya existía (eec95c5, 2026-05-12 16:02). Los 4 traces de error son ANTES (15:40-15:43). Está fixed en código.
- Mejora: detector refactorizado a if-chain (parens-free `or...and` correcto pero ambiguo al leer).
- Bug encontrado: `subset_truncate_retry` log emitía `original=len(...)` después de reasignar la variable → `original == kept` siempre. Fix: capturar `original_count` antes del slice.
- Nuevo test: `test_context_overflow.py` (8 tests) — pin wording del detector + asserta que `_compact_active_history_for_retry` realmente shrink.

### 2b — WinError 10054 (no commit; ya cubierto)
- Inspección: `_post_chat_with_recovery` ya recupera `10054` con health-poll + retry. Cubierto por `test_llm_client_retry::TestPostChatWithRecovery::test_reset_then_healthy_retries_once`.
- En traces reales: el server probablemente no se recuperó en 15s (crash hard), por eso `llm_connection_reset_no_recovery` propagó. Comportamiento esperado.
- **Hallazgo lateral**: `chat_stream` NO usa `_post_chat_with_recovery`. Solo se usa en tests; agent.py no consume streaming aún. Sin impacto activo. Anotado.

### 2c — mission_outcome chitchat noise
- 27/35 mission_outcome del último período = UNVERIFIED de chitchat puro ("hola", "como te llamas").
- Skip requiere decisión de diseño: ¿el outcome debería emitirse cuando `expected_total==0`?
- `🚨 NEEDS DECISION` — ver MORNING_REPORT. Sin código tocado.

## 01:10 — Phase 3: Tool robustness (commit c387258)
- 64 compound tools en ToolRegistry, 63/64 son thin wrappers (3 líneas, delegan a domain_tools/ops_tools).
- `execute()` ya envuelve `impl(impl_args)` en try/except (línea 1659). Handlers no necesitan try outer.
- Cobertura: **agregado `test_tool_dispatch_contract.py`** que pin 5 invariantes de `execute()`: dict siempre, no raise, exception bubble como ok=False, unknown tool graceful, invalid args con validation_errors.

## 01:40 — Phase 4: Pending action (commit 7f66a84)

### Bugs encontrados (ambos en `_extract_profile_name`)

**Bug 1 — P1 productivo**: "olvidalo"/"cancelalo" passed as profile name.
- Root cause: `order_verbs` set comparaba con `==`, no prefix. "olvida" matcheaba pero "olvidalo" no.
- Impacto: si user dice "olvidalo" tras profile prompt → media tool arrancaba con `profile="olvidalo"`, abriendo Disney+ con nombre absurdo.
- Fix: prefix-match con `startswith(root)` + extended root list ("cancel", "dale", "dejalo", "dejame").

**Bug 2 — P2**: "Ema." retornaba "Ema." literal.
- Root cause: rstrip de punctuation solo aplicaba al regex-pattern path, no al bare-name fallback.
- Fix: `s_clean = s.rstrip(" .,;!?")` antes de evaluar.

### Edge cases cubiertos (test_pending_resume.py +16 tests)
- TTL >300s: pending se auto-clear y no resume (test con backdated created_at).
- TTL <300s: resume normal.
- "olvidalo", "cancela", "no importa": pending closed, retorna None.
- Long off-topic: pending preservado para futuro reply on-topic.
- Persistencia entre instancias: segunda `Gemma4Agent(state_path=mismo)` ve el pending.
- Extractor adversarial (10 nuevos casos): acentos, mayúsculas, trailing punct, intent change, yes/no, questions, empty, long, special chars.

## 02:10 — Phase 5: Router corpus (commit aeea7b0)

### Bug encontrado: "Mi perfil es Ema" → router=["email"]
- Path: keyword matching no matchea → semantic fallback (embedding multilingual) → "perfil" similar a email tools.
- Defensivo: `_try_resume_pending_action` corre ANTES del router en producción → no se manifiesta normalmente.
- Fix: negative anchor en `_suggest_tools` Y post-semantic-fallback: si `\b(perfil|profile)\b` sin keyword mail/email/correo → drop email.

### Corpus de regresión: `test_router_corpus.py`
- 33 utterances reales sampleadas de traces (últimos 7 días).
- Aserta hit-rate global ≥75% (medido 100% post-fix).
- Si un cambio futuro al router cae bajo 75%: alerta inmediata.

## 02:35 — Phase 6: Verifiers/guards (commit a851bae)

### Hallazgo: `_DISPATCH_OK_COMPLETIONS` duplicado
- Definido en `tools.py:211` (frozenset, módulo level) y `agent.py:1908` (set local en `_guard_unverified_final`).
- Riesgo drift: agregar entry en uno y olvidar el otro.
- Estaban sincronizados al commit (10 entries idénticas).
- Fix: importar desde `tools` en agent.py. `test_dispatch_status::test_includes_all_observed_dispatch_completions` ya validaba contra logs, ahora valida una única fuente.

### Completions observados en traces — sin huecos
- `launch_verified`, `research_sources_read`, `message_sent`: `verified=True` → pasan primer guard, no necesitan estar en el set.
- `opened_search_results_pending_play`: `verified=False, status=attempted` → guard inyecta nota correctamente (es genuinamente incompleto).

## 02:55 — Phase 7: Adjacent subsystems (commit 599fb2e)

### MCP server hardening (+6 tests)
- Existing: 14 tests cubrían tools/list, initialize, tools/call, notifications.
- Agregados: empty dict, missing method+id, params=str, tools/call sin arguments/None/empty name.
- Total: 20 tests MCP.

### Sin cambios (cobertura ya suficiente)
- `skills_registry.py`: 26 tests existentes cubren yaml parse, eligibility, scan, opt-out, load.
- `loop_detection.py`: 19 tests cubren signatures, repeat warnings, ping-pong, circuit breaker, evidence reset, env opt-out.
- `llm_client.py`: 7 tests cubren retry connection reset + unsupported option fallback.

## 03:15 — Phase 8: DX/perf + reporte

- `import gemma4_agent.agent`: **0.095s** (sin lazy issues).
- `traces.jsonl`: **1.2 MB**, 4834 líneas. No requiere rotación (< 50MB).
- Full pytest: **478 passed, 0 failed** (baseline 440 → +38 tests).
- Stash WIP previo conservado: `pre-night-audit-WIP-2026-05-16`.
- `git status` limpio tras commits.



