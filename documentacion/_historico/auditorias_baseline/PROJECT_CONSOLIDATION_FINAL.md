# Carter Agent — Consolidación final de la auditoría

Documento de cierre de TODA la auditoría: tres sesiones (overnight + continuación
+ cierre), 13 rondas de caza + profundización + guardrails. Fecha: 2026-05-21.

---

## VEREDICTO HONESTO

**Carter Agent está consolidado en arquitectura y fiabilidad. La rama
`PortandoLoMejor` está lista para review, con un único hueco de confianza
acotado (validación LLM E2E) que depende de liberar la GPU.**

No hubo trabajo fabricado en esta sesión de cierre: la Fase 4 (auditar más
rincones) se SALTÓ porque la evaluación honesta — respaldada por 2 rondas limpias
previas, el fuzz de primitivos sin fallos, y un shakedown E2E sin anomalías —
concluyó que no quedan fixes de valor real. El valor de esta sesión fue durable:
guardrails + documentación + un shakedown honesto.

### Confianza por eje

| eje | confianza | fundamento |
|-----|-----------|------------|
| **Arquitectura** | **Alta** | Hot-path (dispatch doble-contención, verifiers, server HTTP, EventBus, vad/audio_io) auditado limpio y ahora con tests de invariante consolidados. Todos los singletons lazy con double-checked locking. 2 rondas de caza terminaron LIMPIAS. |
| **Fiabilidad** | **Alta** | Persistencia atómica + recovery de corrupción, teardown sin huérfanos (handles, server atexit, playwright), diagnósticos fail-safe, primitivos fuzzeados (~18k inputs). Cada invariante con ≥1 test. |
| **Latencia** | **Alta (Python-side) / media (E2E)** | Wake throttle (−74% medido), per-mode timeout, compaction (2.7ms/10MB), microagent cache (−49% _system_message), STT RTF 0.05 sobre voz real. Falta SOLO el TTFT/decode E2E del LLM (GPU ocupada). |

### Qué NO se cubrió y por qué es aceptable

1. **LLM E2E en vivo** (TTFT, decode, cache-reuse de Gemma con --swa-full): las
   3 sesiones tuvieron la GPU ocupada (~6.6 GB) con el usuario potencialmente
   jugando; cargar ~6 GB encima arriesgaba OOM-ear su proceso (CLAUDE.md mand. 6).
   El path está cubierto por tests mockeados (recovery, timeout, dispatch) y
   auditado limpio. Aceptable hasta que RED libere la GPU.
2. **domain_tools.py (10.5k LOC) handler-por-handler**: deuda de mantenibilidad
   conocida, NO de fiabilidad — cada handler está aislado por el doble try/except
   del dispatch. Cubrir 1:1 es bajo payoff.
3. **launcher GUI (pywebview/browser)**: IO de arranque, sólo validable E2E.
4. **Edges no-deterministas** (quarantine rename-fail bajo lock de antivirus):
   documentados en coverage_gaps.md, fail-loud correcto, bajo valor de test.

---

## Acumulado total de todas las sesiones

- **Bugs reales fijados:** **27** (rondas 1–13: 26 + continuación: 1 tracing-ValueError).
  Todos en bordes (lifecycle/teardown/persistencia/recovery/primitivos/diagnósticos),
  NINGUNO en el camino feliz — patrón confirmado 9 veces.
- **Optimización de latencia aplicada:** 1 (cache de microagents, −49% _system_message),
  + validadas en vivo las previas (wake throttle, per-mode timeout, compaction).
- **Tests añadidos (todas las sesiones):**
  - Puntuales por-fix: ~21 archivos (rondas 1–11).
  - Fuzz property-style: test_primitives_fuzz (12, ~18k inputs).
  - Invariantes consolidados: test_architectural_invariants (13).
  - No-orphan: test_no_orphan_resources (4).
  - Perf budget: test_perf_budget (3, @slow/gpu).
  - Smoke tripwire: test_smoke_overnight (18).
  - Coverage gaps: test_llama_server_external_detection (5), +casos en tts-reenable/tracing.
  - Total archivos de test: 102 → **114** (+12 esta auditoría).
- **Suite:** ~1113 passed por batches; **1 rojo PRE-EXISTENTE y ajeno**
  (`test_streaming_profile::test_cdp_success_marks_played`, requiere Chrome CDP
  real; commit anterior a la auditoría; no se tocó streaming).
- **Módulos auditados:** todo el hot-path, always-on de audio, persistencia,
  recovery, daemons/lifecycle, diagnósticos, y los primitivos puros. Mapa completo
  en `docs/ARCHITECTURE.md`.

---

## Guardrails dejados (qué impide que se regrese lo ganado)

1. **`test_perf_budget.py`** (@slow): falla si la compaction, el _system_message,
   o el wake throttle regresan más allá del margen medido. Una regresión de
   latencia ya no pasa silenciosa.
2. **`test_architectural_invariants.py`**: 13 invariantes (dispatch contiene
   excepciones, verifier no tumba el turno, diagnósticos fail-safe, persistencia
   recupera, singletons con lock, server sin huérfanos, etc.) ejercitando código
   real, cada uno citando la ronda que lo originó.
3. **`test_no_orphan_resources.py`**: open/close de recursos deja open_files en
   baseline (psutil, OS-level) + los atexit siguen cableados.
4. **`test_primitives_fuzz.py`**: ~18k inputs aleatorios sembrados sobre los 4
   primitivos puros — caza edge cases que un test puntual no cubre.
5. **`test_smoke_overnight.py`**: tripwire rápido (<2s) de los fixes principales.
6. **`docs/ARCHITECTURE.md`**: el mapa de invariantes para que un cambio futuro
   sepa qué capa está blindada y cuál es de alto riesgo.

---

## Lo que queda en manos de RED (lista corta y accionable)

1. **Validar LLM E2E con la GPU libre** (único hueco de confianza). Correr
   `launcher start-server` + medir TTFT/decode + cache-reuse en vivo.
2. **Decisión de producto — `_inbox` bound** (questions_for_red #4): ¿bound duro
   con toast "estoy ocupado" o unbounded (seguro hoy)? Pregunta de 1 línea ahí.
3. **`gemma4_agent/ContextoClaude.md`** (questions #2): archivo sin trackear que no
   creé yo — ¿gitignore, borrar, o versionar?
4. **El rojo de CDP** (`test_streaming_profile`): marcarlo `skip-if-no-chrome` o
   correrlo en un entorno con Chrome. No es de la auditoría.
5. **Deps bloqueadas (opcional):** si querés property-based + coverage en CI,
   autorizar `hypothesis` + `pytest-cov` (esta sesión los emuló: fuzz sembrado +
   coverage manual).

Sin `tradeoffs.md`: ningún fix de las 3 sesiones mejoró un eje degradando otro.

---

## Recomendación de merge

**La rama `PortandoLoMejor` está lista para review y merge**, con la salvedad de
que la confianza de producción se completa al correr la validación LLM E2E (punto
1). El código de la auditoría es verde, atómico, trazable y guardado por tests de
regresión. Los pendientes son 1 medición (GPU) + 3 decisiones de producto/entorno
— ninguno bloquea el review del código en sí.

Si RED quiere mergear YA: hacerlo, y dejar el LLM E2E como un smoke de
post-merge en cuanto la GPU esté libre. Si prefiere confianza total antes del
merge: correr el punto 1 primero (es ~10 min con la GPU libre).

---

## Procesos al cierre

```
llama-server: none
node.exe:     none
```
Nunca se levantó el server pesado (GPU ocupada). Los modelos del shakedown
(wake/STT) se cargaron en procesos de test efímeros y se liberaron. Sin huérfanos.
