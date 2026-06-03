# Análisis de cobertura — sesión de continuación 2026-05-21

`pytest-cov` / `coverage` NO están instalados (BLOCKED_NEW_DEP). Este análisis es
MANUAL, enfocado en las ramas de **recovery / lifecycle / hot-path** de los
módulos que la auditoría tocó — NO persigo % por vanidad, solo ramas que protegen
un invariante (arquitectura), una ruta de recuperación (fiabilidad) o un path de
latencia.

## Gaps cerrados esta sesión

| módulo | rama sin cubrir | test nuevo | eje |
|--------|-----------------|------------|-----|
| llama_server.start() | detección de server EXTERNO + no-take-over + warning de context-mismatch + (external -> current_profile None, stop() no-op) | test_llama_server_external_detection (5) | fiabilidad |
| llama_server.start() | `skipped_standby` (profile sin server) | idem (test_standby_profile_does_not_start) | fiabilidad |
| voice_runner.enable() | TTS load() FALLA -> voz habilita igual, no arranca worker muerto, re-enable no crashea | test_voice_runner_tts_reenable (nuevo caso) | fiabilidad |

## Ramas YA cubiertas (verificado, no necesitan test nuevo)

- **llama_server.detect_crash_signature**: 5 casos en test_log_audit_fixes
  (cuda_illegal_memory / oom / segfault / context_overflow / none).
- **experience.py recovery**: quarantine+recreate (3 tests en
  test_experience_corruption_recovery) + schema-drift fail-loud RuntimeError
  (test_experience_schema_drift).
- **middle_ellipsis / sanitize_text / _split_clauses / FuzzyCorrector**: fuzz
  property-style (test_primitives_fuzz, ~18k inputs).
- **tracing failsafe**: OSError + ValueError + non-serializable + healthy
  (test_tracing_failsafe, 5 casos).
- **shared_manager / log-handles / pipeline-stop / mcp-registry / redact**:
  cubiertos por sus tests de ronda 11.

## Gaps ACEPTADOS (sin test, con razón)

1. **experience._quarantine_corrupt_db() retornando False** (rename del archivo
   corrupto falla -> `_open` re-raisea). **Por qué aceptable:** la ronda 4 ya
   cierra la conexión antes del rename (evita WinError 32, la causa real); el
   único trigger restante es un lock transitorio de antivirus EN el momento del
   rename, no determinista. Un test requeriría mockear os.replace para raisear —
   frágil y de bajo valor (el comportamiento fail-loud es correcto). Eje:
   fiabilidad, severidad mínima (degradación, no corrupción).

2. **Tracing con path null-byte en `event()`** (no en `__post_init__`, que ya se
   amplió a ValueError en 2e9a48f). event() ya captura (OSError, TypeError,
   ValueError), así que está cubierto por contrato; un path se setea una vez en
   construcción, no por evento. Sin gap real.

3. **domain_tools.py (10.5k LOC, registry de handlers)**: NO se persigue coverage
   exhaustivo — cada handler está aislado por el doble try/except del dispatch
   (execute() + _run_with_timeout). El riesgo de un handler sin test es un error
   de tool (contenido), no un crash del turno. Auditar/cubrir handler-por-handler
   es bajo payoff / alto esfuerzo; queda como deuda de mantenibilidad conocida.

4. **launcher.py run_ui modos pywebview/browser/headless**: GUI/IO de arranque;
   requieren un display real o mocks pesados de webview/uvicorn. El shutdown
   ordenado (server.should_exit + join) está auditado por lectura (ronda 11). Eje:
   arquitectura, validable solo E2E (mismo bucket que el boot real diferido).

## Veredicto

Las ramas de recovery/lifecycle/hot-path relevantes a los tres ejes están
cubiertas o documentadas como aceptables. Los gaps que quedan son (a) IO de
arranque que sólo se valida E2E, o (b) edges no-deterministas de bajo valor. Sin
coverage automatizado no doy un número %, pero el criterio fue cualitativo y
dirigido: cada invariante de las 26 correcciones tiene al menos un test que lo
pinea.
