# LIVE_RUNTIME_CYCLE_4_REPORT

Fecha: 2026-05-05

## 1) Causa real encontrada

La causa principal de la divergencia test vs live fue de **encoding en el harness de smoke**, no de pérdida de `SessionState`:

- el runner enviaba stdin en UTF-8 a un proceso REPL que interpretaba entrada con codepage local;
- `"Sí"` llegaba como mojibake (`SÃ­`);
- `pending_intent_candidate` hacía miss y el flujo caía en trivial.

Evidencia: `LIVE_RUNTIME_CYCLE_4_PENDING_REPRO.md`.

## 2) Por qué el test pasaba y live fallaba

- En test unitario, `engine.run_turn("Sí")` usa string Unicode correcto dentro del mismo proceso.
- En live harness (subprocess), antes del fix, el segundo turno llegaba corrupto.
- El pending sí se guardaba en turno 1; fallaba su consumo en turno 2 por entrada mal decodificada.

## 3) Fix aplicado

### A) Instrumentación temporal (controlada por env var)

- `src/carter_v3/agent.py`
  - logging debug condicionado por `CARTER_DEBUG_PENDING=1`
  - campos: `turn_id`, `user_text`, `has_pending_before`, `pending_tool`, `pending_target`, `pending_ttl`, `pending_candidate_result`, `short_circuit_route`, `mission_status`, estado de pending.
  - salida por `stderr`; sin impacto cuando env var no está activa.

### B) Pending intent estructural (mínimo)

- `src/carter_v3/session_state.py`
  - nuevo `PendingIntent`
  - `remember_pending_intent`, `pending_intent_candidate`, `clear_pending_intent`

- `src/carter_v3/agent.py`
  - consulta pending antes de short-circuit trivial
  - si follow-up corto afirmativo, ejecuta `_run_pending_intent(...)`
  - guarda pending para `filesystem_read_text` cuando outcome no concluyente o detalle de readback no disponible.

### C) Fix del harness (raíz de la divergencia)

- `audit/smoke_live_post_cleanup.py`
  - stdin ahora se codifica con `locale.getpreferredencoding(False)` en vez de UTF-8 fijo.
  - evita mojibake en prompts con acentos (`Sí`) en el REPL live.

### D) Repro mínima de dos turnos

- `audit/repro_pending_intent_live.py`
  - compara:
    - engine directo (misma sesión),
    - REPL subprocess con stdin UTF-8,
    - REPL subprocess con stdin cp1252/local.
  - genera: `LIVE_RUNTIME_CYCLE_4_PENDING_REPRO.md`.

## 4) Por qué NO es hardcode

- No se añadió routing por frases (`if "sí"/"lee"/"alarma" ...`).
- No se añadieron regex semánticos por intención.
- El cambio es de estado estructural (`pending_intent`) + encoding del harness.
- `hardcode_guard` sigue limpio.

## 5) Tests agregados/actualizados

- `tests/test_pending_intent_followups.py`
  - `test_filesystem_read_pending_intent_can_continue_on_yes`
  - cobertura de guardado/consumo pending en dos turnos.

Se mantuvieron verificaciones no-hardcode:
- `tests/test_no_semantic_hardcodes.py`

## 6) Resultado pytest

- `python -m pytest tests/test_pending_intent_followups.py -v` -> `4 passed`
- `python -m pytest tests/test_live_regressions_from_user_log.py -v` -> `5 passed`
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` -> `16 passed`
- `python -m pytest --tb=short` -> `441 passed`

## 7) Resultado hardcode_guard

- `python audit/hardcode_guard.py` -> `clean (56 files scanned)`

## 8) Resultado repro live de 2 turnos

Archivo: `LIVE_RUNTIME_CYCLE_4_PENDING_REPRO.md`

Hallazgo clave:
- UTF-8 stdin -> `Sí` se corrompe (`SÃ­`) y pending miss.
- Local/cp1252 stdin -> `Sí` llega correcto, pending hit y se ejecuta el pending intent.

## 9) Resultado smoke live Cycle 4

Archivo: `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_CYCLE_4.md`

Caso crítico `lee PATH` + `Sí`:
- Turno 1: `filesystem_read_text` no concluyente (honesto).
- Turno 2: ya no cae en trivial; re-ejecuta flujo de lectura pendiente (estado `complete` en salida actual).

## 10) Fallos restantes

Persisten fallos live no resueltos en:
- capacidades ausentes (alarmas/mensajería) con estado final todavía mejorable;
- algunos prompts de persona/capability con variabilidad del LLM local;
- diferencias de pass/fail por criterio de matriz histórica.

## 11) Veredicto

`LIVE_TEXT_CORE_ALMOST_READY`

Razón:
- Se cerró la causa raíz de la divergencia test-vs-live en pending intent.
- Tests + guard están verdes.
- Aún quedan fallos de smoke en capacidades ausentes/consistencia de estado para declarar `LIVE_TEXT_CORE_READY`.

