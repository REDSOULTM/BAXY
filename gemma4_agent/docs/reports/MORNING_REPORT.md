# Morning Report — 2026-05-16

## Resumen ejecutivo

Sesión nocturna sobre `PortandoLoMejor`. **6 commits forward**, **478 tests pasan (era 440)**, **0 regressions**. 2 bugs reales fixed (extractor "olvidalo" como profile name, router → email para "Mi perfil es X"). Resto fue cobertura defensiva (contract tests, edge cases, dedupe de fuente única). Audit completo de los 7 días de traces no encontró P0 activo: los crashes históricos (context overflow, tasklist timeouts) ya estaban fixed por commits del 12-15 may.

## Bugs arreglados

| Commit | Severidad | Resumen |
|---|---|---|
| [`7f66a84`](#) | **P1** | `_extract_profile_name` aceptaba "olvidalo" como perfil → media tool arrancaba con profile="olvidalo" |
| [`7f66a84`](#) | P2 | `_extract_profile_name` no strippeaba trailing punct en bare-name path ("Ema." → "Ema.") |
| [`aeea7b0`](#) | P2 | Semantic fallback enrutaba `"Mi perfil es Ema"` → `["email"]` (pending-resume lo intercepta antes, pero el fallback defensivo no era robusto) |
| [`1912230`](#) | P3 | `subset_truncate_retry` log emitía `original == kept` siempre (reasignación antes del log) |
| [`a851bae`](#) | P3 | `_DISPATCH_OK_COMPLETIONS` duplicado en tools.py + agent.py (drift risk) |

## Tests añadidos: 440 → 478 (+38)

| Archivo | Tests | Cobertura |
|---|---:|---|
| `test_context_overflow.py` (nuevo) | 8 | Detector wording + `_compact_active_history_for_retry` shrink |
| `test_tool_dispatch_contract.py` (nuevo) | 5 | 5 invariantes de `ToolRegistry.execute()` |
| `test_pending_resume.py` (+) | 16 | TTL, explicit cancel, persistence, adversarial extractor (10) |
| `test_router_corpus.py` (nuevo) | 3 | 33 utterances reales, hit-rate ≥75% |
| `test_mcp_server.py` (+) | 6 | JSON-RPC edge cases (empty/missing/None args) |

## `[DEFERRED]` items

- `chat_stream` en `llm_client.py` no usa `_post_chat_with_recovery`. Sin impacto activo (agent.py no consume streaming), pero quedó anotado: cuando agent.py adopte streaming, agregar el wrapper.

## `🚨 NEEDS DECISION` items

1. **`mission_outcome` para chitchat puro**: 27/35 outcomes recientes son `UNVERIFIED` por mensajes conversacionales ("hola", "Soy Gemma 4", "Je peux parler français"). El evaluador emite outcome aunque `expected_total == 0` y `len(events) == 0`. Esto satura los traces y baja la signal-to-noise de métricas. ¿Querés saltar mission_outcome cuando es 100% conversación, o mantenerlo? Pasos para skipear son chicos pero es cambio de semántica que prefiero confirmar.

2. **Warnings `PytestReturnNotNoneWarning` en test_verifiers.py + test_loop_detection.py**: 45+ tests usan `return True/False` en vez de `assert`. Pytest acepta pero warnea. ¿Migrar? Es trivial pero requiere tocar archivos antiguos y prefiero no hacerlo sin tu OK.

## Sugerencias (sin implementar)

- **`browser action=minimize` rebota con "invalid tool arguments"** (1 caso histórico). Mejora UX: detectar acción no soportada y sugerir `window action=minimize`. Cambio chico en `_coerce_and_validate_tool_args` o en el dispatch error.
- **Pre-validation hooks**: `download` retornó "missing url" 1× (validation tardía). Algunos handlers podrían tener pre-validators en el dict `_PRE_VALIDATORS` que ya existe.
- **Trace rotation**: 1.2MB en 7 días = ~62MB/año si crece linealmente. No urgente, pero pensar rotación cuando supere 20MB.
- **WIP stash conservado**: `pre-night-audit-WIP-2026-05-16` tiene cambios en `voice/stt.py` + nuevo `voice/app_inventory.py` + edits a `test_gx_features.py`. Revisar cuando quieras (`git stash show -p stash@{0}`).

## Estado final

- **branch**: `PortandoLoMejor`
- **last commit**: `599fb2e test(mcp): cover JSON-RPC edge cases`
- **baseline commit**: `e70c09b fix(streaming): Disney+ y Max URLs reales`
- **commits forward**: 6
- **tests**: 478 passed / 0 failed
- **import time**: 0.095s
- **traces.jsonl**: 1.2MB (sin rotación)
- **WIP stash**: `pre-night-audit-WIP-2026-05-16` (3 archivos voice/)

## Para tu siguiente sesión

Si querés que arranque otra noche de audit similar, el script `scripts/trace_audit.py` es reusable (`python scripts/trace_audit.py --days 7`). Ahora produce salida más completa (loops, latencies, mission_outcome distribution).

Buen día.
