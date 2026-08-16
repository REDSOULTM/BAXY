# LLM_FIRST_RESPONSE_AUDIT

Fecha: 2026-05-05

## Fuentes leídas

- `../ContextoCarter.md`
- `LIVE_RUNTIME_CYCLE_7_REPORT.md`
- `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_STRICT_CYCLE_7.md`
- `STRICT_LIVE_SMOKE_ORACLES.md`
- `CURSOR_HARDCODE_CONTAMINATION_AUDIT.md`
- `audit/hardcode_guard.py`
- `tests/test_no_semantic_hardcodes.py`

Faltantes declarados y no bloqueantes:

- `MANUAL_SPOTCHECK_FAILURE_AUDIT.md`
- `MANUAL_SPOTCHECK_REPAIR_PLAN.md`

## Hallazgos

| Archivo | Respuesta canned detectada | Ruta | Riesgo | Reemplazo LLM-first | Test necesario |
|---|---|---|---|---|---|
| `src/carter_v3/agent.py` | `_local_short_reply()` devolvía `Hola. ¿Qué necesitas?`, `Sí.`, `De nada.`, `Necesito un poco más de contexto.` | `trivial_lowinfo` / `ambiguous_short` | Alto: saludos, ok, gracias y dudas cortas podían salir sin LLM | Eliminar `_local_short_reply()` y usar `generate_chat_reply(...)` o llamada LLM directa no-tools | `test_trivial_inputs_use_llm_but_no_tools`, guard de literal canned |
| `src/carter_v3/agent.py` | `_scripted_or_llm_short()` tenía fallback determinístico `Sigo aquí...` / `¿Puedes precisar...?` | fallback de short chat si LLM vacío | Alto: fallback normal user-facing sin LLM | Mover fallback a emergency fallback; ruta normal llama LLM | `test_trivial_reply_is_not_fixed_when_llm_output_changes` |
| `src/carter_v3/agent.py` | `followup_status_reply` devolvía texto final estructural directo | follow-up `abriste X?` / `lo cerraste?` | Medio: correcto en facts, pero no LLM-first | Pasar el scaffold de última acción a `generate_result_reply(...)` | tests existentes de follow-up + `test_tool_result_unverified_calls_llm_but_cannot_be_completed` |
| `src/carter_v3/agent.py` | capability/ambigüedad devolvía `compose_missing_capability_reply()` directo | acción sin target/tool verificable | Alto: fallback visible rígido | Verbalizar con facts cerrados y `mission_status=needs_user` | `test_no_tool_calls_action_with_no_target_asks_user`, live regressions |
| `src/carter_v3/agent.py` | unsupported visual devolvía `compose_unsupported_visual_reply()` directo | OCR/visión ausente | Medio: bloqueo correcto pero texto canned | Verbalizar con policy/evidence de capability ausente | `test_unsupported_ocr_request_fails_honestly_without_screenshot` |
| `src/carter_v3/agent.py` | memory offer reparaba corrupción con string fijo | declarative fact + memory offer guard | Medio: aclaración visible fija | LLM verbalizer con instrucción de no repetir texto corrupto | existing corruption + memory offer tests |
| `src/carter_v3/agent.py` | resultado final de tools usaba `compose_default_reply(...)` directo | tool result normal | Alto: `Intenté 1 acción(es)...`, `Abrí X...`, memory recall, filesystem, window_list podían ser plantillas finales | Calcular status estructural primero y pasar `draft_factual_scaffold` + evidence al LLM verbalizer | `test_memory_recall_uses_llm_verbalizer_with_real_fact`, `test_tool_result_unverified_calls_llm_but_cannot_be_completed` |
| `src/carter_v3/response_composer.py` | múltiples templates rígidos (`No tengo una capacidad verificable...`, `Intenté...`, `Recuerdo esto...`, etc.) | composer evidence-based | Medio: aceptable solo como scaffold interno; no debe ser ruta normal final | Mantener como factual scaffold/guard, no como normal final | full suite + guard fake-success |
| `src/carter_v3/cli/launcher.py` | fallback fatal/launcher/scripted `Hola, soy Carter.` / `(modo stub)` | bootstrap/debug | Bajo: fuera del chat normal o modo stub | Documentado como excepción técnica/launcher; runtime normal usa engine verbalizer | No requiere test LLM-first de chat normal |
| `audit/hardcode_guard.py` | no detectaba literales triviales canned exactos | CI guard | Medio: podía reintroducir saludos fijos | Añadir `canned_trivial_reply_literal` | `test_canned_trivial_reply_literal_fails` |
| `tests/test_runtime_persona_and_capabilities.py` | validaba prompt/persona, no ruta final LLM-first | tests | Medio: no detectaba triviales sin LLM | Mantener prompt tests y añadir `tests/test_llm_first_responses.py` | nuevo suite LLM-first |
| `audit/smoke_live_strict.py` | oráculo aceptaba `Hola. ¿Qué necesitas?` como PASS histórico | smoke strict | Medio: resultado histórico, no criterio nuevo | Crear manual-equivalent smoke que rechaza fixed canned para Hola | `audit/smoke_manual_equivalent.py` |

## Conclusión de auditoría

Había rutas normales donde el texto visible podía salir sin LLM: trivial, ambiguous short, follow-up de acción previa, capability missing, unsupported visual, policy block y tool-result composer. La implementación nueva introduce una capa LLM-first para esas rutas, mantiene composer solo como scaffold estructural y endurece el guard contra literales triviales canned.
