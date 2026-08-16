# LIVE_RUNTIME_CYCLE_3_REPORT

Fecha: 2026-05-05

## 1) Baseline post-cleanup
- `git commit`: `db768b7e` (`Clean semantic hardcodes and harden guard`)
- `python -m pytest --tb=short` -> `439 passed` (baseline inicial del cycle)
- `python audit/hardcode_guard.py` -> `clean (56 files scanned)`
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` -> `16 passed`

## 2) Blockers antes (post-cleanup re-smoke)
Documentados en:
- `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_POST_CLEANUP.md`
- `LIVE_RUNTIME_POST_CLEANUP_BLOCKERS.md`

## 3) Fixes aplicados en Cycle 3 (sin hardcode)

Se aplicaron 4 cambios máximos del plan, todos estructurales:

1. `src/carter_v3/request_patterns.py`
   - Endurecimiento de deícticos para evitar falsos positivos de acción en inputs triviales.
   - Reintroducción de extracción estructural de rutas Windows (`extract_windows_path`) y síntesis de `filesystem_read_text` por forma (no por frases).

2. `src/carter_v3/agent.py`
   - `looks_action` activado por presencia estructural de ruta Windows (`extract_windows_path`) para habilitar tool routing honesto.

3. `src/carter_v3/turn_support.py`
   - `select_tools()` ahora incluye `filesystem_read_text` cuando se detecta un path absoluto Windows por forma.

4. `src/carter_v3/guards.py`
   - `fake_success_guard` endurecido para claims futuros con hora sin confirmación de tool (`future_time_claim_without_confirmation`), con patrón estructural de tiempo.

## 4) Tests actualizados

Se actualizaron/extendieron tests permitidos:
- `tests/test_live_regressions_from_user_log.py`
  - `test_windows_path_plus_si_followup_works`: exige tool call estructural `filesystem_read_text` con path esperado.
  - `test_typo_greeting_is_not_action`: vuelve a exigir `TRIVIAL` y sin tool calls para `HGOla`.
- `tests/test_runtime_no_fake_success_live_cases.py`
  - nuevo test `test_fake_success_guard_blocks_future_time_claim_without_confirmation`.

## 5) Validación local final

- `python -m pytest --tb=short` -> `440 passed`
- `python audit/hardcode_guard.py` -> `clean (56 files scanned)`
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` -> `16 passed`

## 6) Smoke live final (Cycle 3)

Archivo:
- `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_CYCLE_3.md`

Resumen:
- prompts: `26`
- pass: `19`
- fail: `7`

Mejoras claras vs post-cleanup inicial:
- `HGOla` pasó a `TRIVIAL` seguro (sin tool routing ambiguo).
- follow-ups de app (`abriste/cerraste`) siguen estables y honestos.
- `app_open` preexisting para Steam mantiene respuesta basada en evidencia.
- no regressions en hardcode_guard / no-semantic-hardcodes.

## 7) Fallos restantes

Persisten bloqueadores relevantes para READY:
- pending intent de lectura filesystem (`lee path` + `Sí`) no cierra de forma estructural robusta.
- ausencia de capability de alarmas aún cae en estado/respuesta no totalmente alineada a flujo de acción (`TRIVIAL` en vez de `NEEDS_USER` consistente).
- prompts de “mensaje a tercero” permanecen en respuesta conversacional del LLM (sin tool real), requieren contrato más fuerte de “capability missing” para acciones externas.

Detalle en:
- `BLOCKERS_CYCLE_3.md`

## 8) Veredicto

`LIVE_TEXT_CORE_NOT_READY`

No se declara `READY` porque, aunque tests+guard están limpios y hubo mejora en smoke, todavía quedan bloqueadores en pending-intent/capability-state para casos críticos del runtime real.

