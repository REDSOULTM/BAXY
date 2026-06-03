# Reporte de sesión de continuación — Carter Agent — 2026-05-21

Continuación de la auditoría (rondas 1–13, 26 bugs). Esta sesión NO fue caza de
bugs en bordes (eso se agotó con 2 rondas limpias) sino **profundizar confianza
(fuzz, coverage), recuperar latencia segura, y dejar la rama lista para review**.

## Resumen ejecutivo por eje

- **ARQUITECTURA:** sin cambios estructurales (el hot-path ya estaba sólido). Se
  cerró por test el branch de detección de server externo, que es el invariante
  del que cuelga el atexit de la ronda 11.
- **FIABILIDAD:** 1 fix (tracing disabilita ante path malformado, no solo
  OSError) + fuzzing property-style de los 4 primitivos puros (~18k inputs, cero
  violaciones) + 2 gaps de coverage cerrados (external-server, TTS-load-fail).
- **LATENCIA:** 1 optimización medida y pura — cache de microagents por firma de
  directorio: `_system_message` 2.08ms → 1.06ms (−49%/turno), sin cambiar
  comportamiento (live-edit preservado, verificado por test).

## Blockers resueltos vs los que quedan para RED

| # | item | estado |
|---|------|--------|
| 5 | tracing crashea con path null-byte (ValueError) | ✅ RESUELTO (2e9a48f) |
| 1 | boot E2E con server real | ⏸️ queda (necesita GPU libre; no es bug) |
| 2 | `ContextoClaude.md` sin trackear | ↪️ RED (no toco lo que no creé) |
| 3 | middle_ellipsis +3 (ya resuelto antes) | ✅ sin acción pendiente |
| 4 | `_inbox` unbounded | ↪️ RED — decisión de producto. **Pregunta refinada:** ¿bound duro (32) que RECHAZA con toast, o unbounded (seguro hoy)? Acotar con drop-oldest descartaría turnos de usuario en silencio (viola "no degradar en silencio"). |

## Tests nuevos (con eje pin-eado)

| test | qué pinea | eje |
|------|-----------|-----|
| test_primitives_fuzz (12) | middle_ellipsis/sanitize_text/_split_clauses/FuzzyCorrector — invariantes sobre ~18k inputs sembrados | fiabilidad/UX |
| test_llama_server_external_detection (5) | standby + external-server protection + context-mismatch + (external→atexit no-op) | fiabilidad |
| test_voice_runner_tts_reenable (caso nuevo) | voz habilita aunque el TTS no cargue; no arranca worker muerto | fiabilidad |
| test_microagents_cache (5) | cache-hit sin read + edit/add/remove invalidan (live-edit) | latencia/fiabilidad |
| test_tracing_failsafe (caso nuevo) | path malformado disabilita, no crashea | fiabilidad |

## Optimizaciones aplicadas (antes/después medido)

| optimización | métrica | antes | después |
|--------------|---------|-------|---------|
| cache de microagents | `load_microagents()` warm | 1.16 ms (re-lee 7 archivos) | 0.20 ms (solo stat) — 6× |
| (idem) | `_system_message()` warm | 2.08 ms | 1.06 ms — **−49%** |

Detalle + cProfile en `bench/latency_microagents_cache.md`. NO apliqué el mismo
cache a `project_context.load_context` (0.47ms, la mitad del payoff, y sin
GEMMA4.md presente son solo ~246µs) — anotado, bajo valor.

## Cobertura por eje + gaps aceptables

Sin `coverage` (BLOCKED_NEW_DEP) → análisis manual dirigido a recovery/lifecycle/
hot-path (ver `audit/coverage_gaps.md`). 3 gaps cerrados con tests. Gaps
aceptados con razón: quarantine rename-fail (no determinista), domain_tools 10.5k
(deuda conocida, aislada por dispatch), launcher GUI (sólo E2E). Cobertura
cualitativa: cada invariante de las 26 correcciones tiene ≥1 test que lo pinea.

## Estado de la rama (resumen de branch_readiness.md)

- Suite completa **~1113 passed** en batches; **1 rojo PRE-EXISTENTE** y ambiental
  (`test_streaming_profile::test_cdp_success_marks_played`, requiere Chrome CDP;
  último commit c54f032 anterior a la auditoría; esta sesión no tocó streaming).
- Commits atómicos, sin reescritura de historia, sin push.
- Falta para mergear: validación E2E con GPU + 3 decisiones de RED (#1/#2/#4 +
  cómo manejar el rojo de CDP). Ninguna bloquea el review del código.

## Acumulado total del proyecto (todas las sesiones)

- **Bugs reales fijados:** 26 (rondas 1–13) + 1 esta sesión (tracing ValueError) = **27**.
- **Optimizaciones de latencia aplicadas:** 1 nueva (microagent cache) +
  validadas en vivo las previas (wake throttle, per-mode timeout, compaction).
- **Tests nuevos esta sesión:** 12 fuzz + 5 external-detection + 5 microagent-cache
  + 2 casos (tts-fail, tracing-malformed) = **24 tests**.
- **Suite:** ~1113 passed, 1 rojo pre-existente ajeno.
- **Patrón confirmado (9ª vez):** el hot-path y los always-on cuidados están
  sólidos; lo que quedaba era profundizar (fuzz/coverage) y recuperar latencia
  Python-side — no más bugs de borde.

## Próximos pasos para RED

1. Liberar la GPU y correr el boot E2E (questions #1): TTFT, boot_progress,
   cache-reuse de Gemma en vivo. Es el último hueco de confianza.
2. Decidir el bound de `_inbox` (questions #4, pregunta de 1 línea).
3. Decidir `ContextoClaude.md` (questions #2) y cómo manejar el rojo de CDP
   (skip-if-no-chrome vs entorno con Chrome).
4. Si querés property-based + coverage automatizado en CI: autorizar `hypothesis`
   + `pytest-cov` (esta sesión los emuló: fuzz sembrado + coverage manual).

## Procesos limpios (cierre)

```
llama-server: none
node.exe:     none
```
Nunca levanté el server pesado (GPU ocupada + usuario potencialmente jugando).
git status limpio salvo artefactos pre-existentes ajenos (ContextoClaude.md + 2
zips de auditoría externa).
