# Estado de la rama `PortandoLoMejor` — listo para review de RED

Fecha: 2026-05-21. Resumen del estado de la rama tras la auditoría completa
(rondas 1–13) + la sesión de continuación (fuzz / coverage / latencia).

## Suite completa: VERDE (1 rojo pre-existente no relacionado)

Corrida en batches (el `-q` de directorio entero crashea por un access-violation
NATIVO de torch/onnx/sounddevice en cierto orden de colección — gotcha
pre-existente documentado, NO un fallo de test). Agregado de los batches:

| batch | passed |
|-------|--------|
| 1 (sesión continuación + audit) | 159 |
| 2 (router/planner/modes) | 99 |
| 3 (tools/verifiers/persistencia) | 314 (+3 subtests) |
| 4 (voice/mcp/integraciones) | 209 |
| 5 (prompt/history/contracts) | 248 |
| 6 (browser/streaming/gui) | 68 |
| streaming_profile (aislado) | 16 |
| **TOTAL** | **~1113 passed** |

**1 rojo PRE-EXISTENTE:** `test_streaming_profile.py::TestCDPHappyPath::
test_cdp_success_marks_played` — requiere una conexión CDP a un Chrome real
(Netflix `via_cdp`). Último commit del archivo: `c54f032`, ANTERIOR a toda la
auditoría. Esta sesión NO tocó nada de streaming/CDP (los únicos archivos no-test
tocados fueron `microagents.py` y `tracing.py`). Es un fallo ambiental, no de
código.

## Commits de la auditoría (atómicos, un fix = un commit)

Sesión overnight + continuación (los más recientes, todos con footer
Co-Authored-By y body conectado a los tres ejes):

```
265a73c perf(latency): cache de microagents (-49% _system_message)
198576c docs(audit): Fase 3 coverage manual
e42cbef test(coverage): voice enable degrada bien sin TTS
dab3cda test(coverage): external-server detection branch
313e545 test(fuzz): property-style fuzzing de primitivos
9ad4b8f docs(audit): Fase 1 blockers
2e9a48f fix(reliability): TraceLogger disables on malformed path
e053f21 docs(audit): rondas 12-13 LIMPIAS
83bf57b docs(audit): reporte overnight
5485143 test(overnight): Fase 3 validación en vivo
8422dd6 test(overnight): 18 smokes + tighten middle_ellipsis
3e918c5 fix(reliability): restart TTS worker on re-enable
5ddd89b fix(reliability): VoicePipeline.stop() resets state machine
13aa71f fix(reliability): atomic Piper voice download
f50dfc1 fix(reliability): stop managed llama-server on exit + lock
7f22ae4 fix(reliability): close parent-side log handles
fb5bb6e fix(reliability): redact_sensitive no crash on numpy
... (rondas 1-10 antes: 21 fixes previos)
```

NO se reescribió historia, NO se rebaseó, NO se pusheó. La rama está 323 commits
adelante de `main` (es una rama de port de larga vida; la auditoría aportó ~24).

## Cobertura por eje (cualitativa — sin coverage tool, BLOCKED_NEW_DEP)

- **ARQUITECTURA:** hot-path del turno (dispatch doble-contención, verifiers,
  server HTTP, EventBus snapshot-then-iterate, vad/audio_io, state, boot daemons)
  auditado limpio. Todos los singletons lazy con double-checked locking. **Alto.**
- **FIABILIDAD:** persistencia (state/experience/telemetry/sessions atomic),
  recovery (server reload, DB quarantine, external-server protection), teardown
  (playwright, log-handles, server atexit, pipeline reset, TTS re-enable),
  diagnósticos fail-safe (tracing, loop-detector). Fuzz en los primitivos. **Alto.**
- **LATENCIA:** per-mode timeout (validado), wake throttle (74% medido),
  compaction (validado), microagent cache (-49% _system_message medido). **Alto**
  en lo Python-side; el costo dominante (LLM prefill/decode en GPU) sólo se
  valida E2E — pendiente (GPU ocupada).

## Qué FALTA para mergear

1. **Validación E2E con GPU libre** (no bloqueante para el código, sí para la
   confianza de prod): boot real + TTFT + cache-reuse de Gemma en vivo. Único
   hueco grande, diferido por la GPU en uso. Ver questions_for_red #1.
2. **Decisión de RED sobre `_inbox` bound** (questions #4): cambio de
   comportamiento visible, no lo toco unilateralmente.
3. **Decisión de RED sobre `ContextoClaude.md`** (questions #2): archivo sin
   trackear que no creé yo.
4. **El rojo de `test_streaming_profile`** es ambiental (necesita Chrome CDP); o
   se marca `@pytest.mark.requires_cdp`/skip-if-no-chrome, o se corre en un
   entorno con Chrome. Decisión de RED (no lo toco: no es de la auditoría).

## Qué NO necesita decisión (listo)

- Las 26 correcciones de fiabilidad/arquitectura + la optimización de latencia
  están commiteadas, testeadas y verdes.
- Property-fuzz sobre los 4 primitivos puros.
- Gaps de coverage relevantes cerrados o documentados como aceptables
  (`coverage_gaps.md`).

## Veredicto

La rama está **lista para review**. El código de la auditoría es verde, atómico
y trazable. Los únicos pendientes son (a) una validación E2E que requiere la GPU
libre y (b) 3 decisiones de producto/entorno de RED — ninguna bloquea el review
del código en sí.
