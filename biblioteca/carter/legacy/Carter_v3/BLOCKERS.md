# BLOCKERS — Carter v3

Estado actual: `TESTS_PASS_BUT_RUNTIME_WEAK` (auditoría Claude Code, 2026-05-06)

Ver análisis completo en `docs/audit/CLAUDE_CARTER_V3_AUDIT_VERDICT.md`.

---

## Bloqueadores activos (pre-voz/pre-cámara)

| # | Bloqueador | Archivo | Prioridad |
|---|---|---|---|
| B1 | Working tree no commiteado — tag `carter-v3-18x30-true-ready` no describe el código en disco (+202 líneas diff) | git | INMEDIATO |
| B2 | `"Sí"`, `"OK"`, `"YES"` no activan `pending_intent` — follow-ups de confirmación rotos | `session_state.py:_short_same_language_nonsecret` | ALTA |
| B3 | `fake_success_guard` solo cubre inicio de reply — claims a mitad de texto no bloqueados | `guards.py:fake_success_guard` | ALTA |
| B4 | `notify_toast` usa `synchronous_ok` → CONFIRMED sin verificación visual real | `tools/catalog.py` | MEDIA |
| B5 | Sin progress reporting en misiones compuestas — silencio hasta que termina | `agent.py` loop de steps | MEDIA |
| B6 | System prompt dice "call it now" — puede ejecutar cuando usuario solo pregunta capacidad | `turn_support.py:build_messages` | MEDIA |

## Gaps de validación (no son bugs de código, son evidencia faltante)

- Sin validación live de `app_open/close` real con modelo LLM corriendo
- Sin medición de latencia real en CI (C15 inválida en modo scripted)
- Sin spotcheck manual completo documentado

## Qué ya está cerrado

- hardcode_guard: LIMPIO (58 archivos)
- fake_success en inicio de reply: BLOQUEADO
- política de seguridad: 20+ patterns activos
- memoria SQLite: funcionando con secret filter
- local reminders SQLite: funcionando
- 490 tests pasan con ScriptedAdapter
