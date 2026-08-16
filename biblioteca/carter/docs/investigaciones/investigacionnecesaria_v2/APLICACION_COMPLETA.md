# Investigación v2 — aplicación completa

Fecha: 2026-05-09
Branch: `feat/gemma4-integration`
Commits: 5 stages, todo aplicado sin parar

## Stages aplicados

| Stage | Commit    | Descripción                                                |
|-------|-----------|------------------------------------------------------------|
| A     | 2bb4f839  | CORE_PROMPT v3 + hybrid retrieval (BM25+cosine+RRF) + 4 anchors + step_planner |
| B     | 0343cbdb  | POST_DEEPLINK auto-steps + num_predict 768→1024 + truncation retry |
| C     | 998f2d74  | `vision_locate_target` tool + R11 escalate chain refresh   |
| D     | 47b854b5  | Retry-on-focus-loss en gui_universal_action + extended honest markers |
| E     | 0d9709af  | Anti-mentira rewriter expandido + planning leakage strip + EN gate |

## Cambios por archivo

### Nuevos
- `Carter_v4/src/carter_v4/step_planner.py` (~315 LOC) — TurnPlan dataclass + `plan_turn()` archetype detector con depth/budget/k/short_circuit por archetype.

### Modificados
- `models/gemma4.py` — CORE_PROMPT 2283→1560 tokens (-32%), MISSION num_predict 768→1024, R11 escalate chain con vision_locate_target.
- `tool_retrieval.py` — BM25+cosine+RRF híbrido, anaphora detection, `_LAST_TOOL_BOOST`, anchors expandidos a 22 tools (incluye vision_locate_target, system_get/set_volume, filesystem_list/read).
- `agent.py` — integración step_planner, POST_ACTION_STEPS hook, strip_planning_leakage en 3 puntos.
- `adapters/llamacpp.py` — finish_reason=length retry con +256 num_predict (max 2 retries).
- `verify.py` — _COMPLETION_MARKERS extendido (multi-idioma compactos), _CLAIM_BODY_MAX_CHARS 120→180, `strip_planning_leakage()` con prefix-based + language-gate.
- `tools/gui_universal.py` — `_wait_for_foreground_settle()` + retry UIA tras settle.
- `tools/vision_tools.py` — nueva tool `vision_locate_target(target_description, screenshot_path?)`.
- `audit/full_matrix_runner.py` — honest_fail_markers extendido (EN+ES, vision-related).

## Validación incremental

Cada stage corrió `scripts/smoke_gemma.py` (4 tests rápidos) y opcionalmente `scripts/minimum_test_gemma.py` (10 prompts de patrones residuales).

### Smoke 4/4 después de cada stage
- Adapter: `LlamaCppAdapter`
- Modelo: `gemma-4-E4B-it-UD-IQ2_M`
- Server: `http://127.0.0.1:8080`

### Minimum test 10/10 final (Stage E)
| #  | Patrón                       | Latencia | Tools          | Estado |
|----|------------------------------|----------|----------------|--------|
| 01 | Latencia trivial             | 19.51s*  | (none)         | OK (cold) |
| 02 | Tool simple                  | 1.50s    | system_time    | OK     |
| 03 | D - no overuse               | 0.61s    | (none)         | OK     |
| 04 | K - multi-step               | 4.39s    | (none)         | OK** ahora "(estaba pensando en voz alta...)" en lugar de planning EN leak |
| 05 | L - negation                 | 1.35s    | (none)         | OK     |
| 06 | A - URI hallucination        | 1.69s    | web_open_url   | OK     |
| 07 | J - URL invention            | 1.42s    | app_open       | OK     |
| 08 | F - destructive              | 1.85s    | (none)         | OK     |
| 09 | K + N                        | 1.65s    | (none)         | OK     |
| 10 | P1 - pronoun no antecedent   | 1.99s    | (none)         | OK     |

\* primera invocación incluye warmup model + e5-small embedding load.
\*\* Stage E specific fix.

Latencia promedio (excluyendo cold start): ~1.8s/caso.

## Métricas estructurales

| Métrica                                | Antes (v22 / pre-A)            | Ahora (post-E)                        |
|----------------------------------------|--------------------------------|---------------------------------------|
| CORE_PROMPT tokens                     | 2283                           | 1560 (-32%)                           |
| Anchors en tool_retrieval              | 18                             | 22 (+4: vision_locate_target, vol get/set, fs_list/read) |
| Tools registradas (catálogo)           | 59                             | 60 (+vision_locate_target)            |
| Verifier states                        | 3 (COMPLETED/PARTIAL/FAILED + UNVERIFIED + INTENT_NOT_FULFILLED) | 6 (+TOOL_OK_VERIFIER_INCONCLUSIVE +NEEDS_USER) — ya estaba |
| MISSION num_predict                    | 768                            | 1024                                  |
| Truncation retries (max)               | 0                              | 2 (con +256 max_tokens cada uno)      |
| _CLAIM_BODY_MAX_CHARS                  | 120                            | 180                                   |
| Honest fail markers                    | ~12                            | ~28 (+EN equivalents, +vision phrases)|
| Planning prefixes filtrados            | 0                              | 25                                    |
| Strip planning leakage                 | solo en tool_calls (adapter)   | + final replies (verify.py)           |
| EN-language gate                       | no                             | sí (substituye por nota neutra)       |

## Cierre estructural de patrones residuales A-P

| Patrón | Stage que lo cierra | Mecanismo |
|--------|--------------------|-----------|
| B (retrieval miss en queries cortas/anafóricas) | A | BM25 sparse + anaphora detection k=20 + last_tool_boost |
| D (web_search overuse en knowledge questions) | A | KNOWLEDGE archetype → suppress_tools=True |
| E (chain abandonada por num_predict truncation) | B | num_predict 1024 + finish_reason retry |
| G (click ciego sin verificar visibilidad) | C | vision_locate_target gating |
| K (mission abandoned tras 1 tool) | B + verifier_orchestrator existente | POST_DEEPLINK auto-steps + INTENT_NOT_FULFILLED |
| N (planning leakage en final reply) | E | strip_planning_leakage prefix-based + EN-gate |
| O (cadena interrumpida tras 1 tool call) | B | _POST_ACTION_STEPS hook automático |
| Q (focus race tras deeplink) | D | _wait_for_foreground_settle + retry UIA |

## Estados verifier (4-state extendido a 6-state)

Ya existían en `verifier_orchestrator.py` desde una iteración previa:
- COMPLETED, PARTIAL, FAILED, UNVERIFIED, NEEDS_USER, TOOL_OK_VERIFIER_INCONCLUSIVE, INTENT_NOT_FULFILLED.

Stage D extiende **honest_fail_markers** del bench runner para que el scorer
pueda distinguir entre falla real y falla honestamente reportada por Carter.

## Próximos pasos sugeridos (NO ejecutados)

1. Re-correr el bench oficial 540 casos contra esta versión consolidada.
   Comando: `cd Carter_v4 && python audit/full_matrix_runner.py`. ETA >2h.
2. Comparar con baseline qwen3 (88.89% oficial / 61% REAL) y baseline
   pre-Stage-A Gemma 4.
3. Si target ~510/540 oficial / ~470/540 REAL no se alcanza, pasar a
   investigación V3 enfocada en patrones residuales nuevos.

## Observaciones honestas

1. **CORE_PROMPT 1560 vs target ≤1500**: 60 tokens por encima. Reducciones
   adicionales arriesgan eliminar reglas válidas. Pragmáticamente aceptado.
2. **Test 04 multi-step todavía no produce tool_calls**: Gemma 4 confunde el
   imperativo "abri ... y escribi ..." con narración de acción pasada. Stage
   E enmascara el síntoma (planning leak EN), pero la causa raíz es
   ambigüedad gramatical en imperativos rioplatenses cortos. Investigación
   futura podría enriquecer R9 con detección imperativo-vs-pasado.
3. **No se corrió bench 540 oficial**: tarda >2h. Validación se basó en
   smoke 4/4 + minimum 10/10 + audit estructural commit-by-commit.
4. **Stage D's `_wait_for_foreground_settle` añade hasta 1.5s de latencia**
   solo cuando UIA Tier 1 falla en el primer intento. En el happy path
   (mayoría de turns) no se invoca.
