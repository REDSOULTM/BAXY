# Sprint 8a — Log (routing infra, sin regex)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** `9401133` `docs(sprint8): prompts for Sprint 8a/8b/8c …`
- **Final code commit:** `ddee83b` `sprint8a.4: opt-in v2 routing …`
- **Net delta vs base:** 4 files, **+776 LOC** (router_v2 + tests + bootstrap + agent wiring)
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged)
- **Suite total:** 790 passed, 1 pre-existing failure (unchanged from Sprint 3a)

## Headline

Infra del router universal sin regex está lista y **default OFF**.
El módulo nuevo (`gemma4_agent/router_v2.py`) implementa la pipeline
de 4 layers del paper de Claude Research May 2026:

- Layer 0: semantic LRU cache (cosine > 0.88)
- Layer 1: smalltalk gate via **delta** entre centroides (no
  absoluto — finding crítico de calibración)
- Layer 2: hybrid retrieval (BM25 + dense e5-small + RRF k=60)
- Layer 3: confidence-gated popular fallback

Sprint 8b va a enriquecer las 65 descriptions con `purpose +
example_queries`; sin eso el BM25 tiene poco material y muchos
queries reales rutean por hybrid sin top-1 confidente. Esto es
**esperado y diseñado** — la infra está lista para que 8b/8c la
calibren con datos reales.

## 8a.1 — Bootstrap script — commit `76ee15e` ✅

`scripts/bootstrap_e5_small.py` (81 LOC). Idempotente. Descarga
`Xenova/multilingual-e5-small` int8 ONNX (~113 MB) +
tokenizer + configs a `~/.gemma4/models/e5-small/`. Re-correr
imprime "already complete" y sale en < 1 s.

**Decisión BM25:** mantener `rank-bm25` (ya instalado). `bm25s`
sería 500× más rápido pero para 65 docs la diferencia es sub-ms;
no vale una dep nueva.

**Hallazgo del smoke pre-flight (queda en commit message):** el
ONNX export necesita `token_type_ids` (BERT-style); la doc de
huggingface NO lo dice. Sin eso el `session.run()` lanza
`ValueError: Required inputs ['token_type_ids'] are missing`.
`router_v2._encode_batch` siempre los pasa como zeros.

## 8a.2 — `router_v2.py` — commit `a0755b8` ✅

415 LOC. Singleton lazy-loaded. Pipeline completa con telemetry
estructurada (`source`, `elapsed_ms`, `top_score`, `dense_top1`,
`bm25_top1`, `smalltalk_sim`, `tools_sim`, `smalltalk_delta`,
`fallback_applied`).

**Hallazgo crítico de calibración (queda en docstrings):**

El esqueleto del prompt usaba thresholds absolutos:
`SMALLTALK_THETA=0.55`, `TOOLS_THETA=0.35`, `FALLBACK_THETA=0.30`.
Esos valores son **inutilizables** con e5-small int8 ONNX:

1. **Smalltalk gate no funciona con absolutos.** e5-small embeddings
   son lo bastante densos que cualquier query lanza un cosine de
   0.85-0.95 contra cualquier centroide. Probé:

   ```
   query                                  smalltalk  tools
   "hola, como estas?"                    0.903      0.870
   "thanks"                               0.931      0.870
   "gracias"                              0.947      0.872
   "abrime el Steam"                      0.903      0.889
   "Puedes hacerme un power point?"       0.865      0.853
   ```

   Sólo el **delta** (smalltalk − tools) discrimina:
   - smalltalk-y queries: delta +0.03 .. +0.08
   - tools-y queries: delta +0.01 .. +0.02 (o negativo)

   Cambié a `SMALLTALK_DELTA_THETA=0.025`. Ahora la gate dispara
   correctamente para greetings/thanks y deja pasar comandos.

2. **`FALLBACK_THETA=0.30` era un error de unidad.** Con RRF k=60
   sobre 65 docs, el top-1 teórico máximo (documento que es #1 en
   AMBOS rankings) es `2 × 1/61 ≈ 0.033`. Con `0.30` TODOS los
   queries habrían disparado el popular-fallback. Corregido a
   `0.025` (~75% del máximo teórico, deja pasar coincidencias
   genuinas y dispara cuando ningún tool calza).

**Smoke probe end-to-end:**

| query | source | top tools |
|---|---|---|
| "hola, como estas?" | smalltalk | [] |
| "thanks" | smalltalk | [] |
| "abrime el Steam" | hybrid | `steam` (top-1) |
| "Puedes hacerme un power point?" | hybrid | `office` en top-3 |
| "ouvre Chrome" | (cache hit accidental con "Steam" a 0.88) | falso positivo conocido |
| "investiga quién ganó la copa 2022" | smalltalk | [] (falso positivo conocido) |

Los dos falsos positivos son **exactamente lo que 8b/8c resuelven**:
8b enriquece descriptions con `example_queries` (BM25 tendrá material
para "Netflix", "investiga", etc), 8c afina thresholds y revisa el
cache CACHE_THETA contra datos reales.

## 8a.3 — `test_router_v2.py` — commit `26ef74f` ✅

22 tests en 4 clases:

- **EnvFlagsTest (3):** `is_enabled` / `is_shadow` falsos sin env,
  `is_shadow` true con env set. Corren siempre (no necesitan modelo).
- **ConstantsSanityTest (4):** pina cada threshold calibrado en su
  banda esperada (`CACHE_THETA ∈ [0.85, 0.95]`,
  `SMALLTALK_DELTA_THETA ∈ [0.01, 0.10]`, etc). Anti-drift contra
  cambios silentes.
- **DisabledPathTest (1):** `route_v2()` devuelve `([], source=disabled)`
  cuando `_load_failed=True`. Patcheamos la sticky flag directamente
  para que el test no dependa del FS.
- **RouterV2BasicTest (10) [skip-if-no-model]:** is_available,
  smalltalk ES + EN, steam routes a steam, "power point" surface
  `office` en top-K (el bug que motivó Sprint 8), top-K cap respetado,
  telemetry shape, warm latency < 300 ms, cache hit en repeat,
  bm25_top1 verificado con explicit `RouterV2.reset()` para forzar
  hybrid en vez de cache.
- **RouterV2EdgeCasesTest (3) [skip-if-no-model]:** empty / whitespace
  query → `empty_query`, module-level `route_v2()` works.

Resultado: 22/22 verde en este host. En hosts sin el modelo (CI
limpio sin bootstrap) solo corren las 8 unconditional tests.

## 8a.4 — Wire opt-in en agent.py — commit `ddee83b` ✅

`agent.run_content` ahora invoca `router_v2` en dos modos:

- `GEMMA4_ROUTER_V2_SHADOW=1`: v1 sigue siendo la pick **autoritativa**.
  Se ejecuta v2 en paralelo solo para **loguear el comparativo** en
  un trace event `router_v2`. Cero cambio de comportamiento. Es lo
  que vamos a correr en Sprint 8c en producción.
- `GEMMA4_ROUTER_V2=1`: v2 subset **reemplaza** v1. Persona /
  continuation / cap pipeline siguen aplicando aguas abajo.

Event shape:

```
router_v2
  shadow: bool
  v2_subset, v1_subset: list[str]
  agreement, disagreement_v2_only, disagreement_v1_only: list[str]
  source: cache|smalltalk|hybrid|empty_query|disabled
  elapsed_ms, top_score, dense_top1, bm25_top1, smalltalk_*
  fallback_applied: bool (only when triggered)
```

Si router_v2 mismo lanza, emite `router_v2_error` y cae a v1 — los
turns nunca se rompen por telemetry.

**Smoke test shadow mode** (query "abrime el power point"):
- v1 → `['office', 'verify', 'state', 'session']`
- v2 → `['accessibility', 'device_settings', 'office', 'package',
       'memory', 'state', 'network', 'terminal']`
- agreement: `['office', 'state', 'verify']`

Coincidencia en el tool clave (`office`) — buena señal para 8c.

## Final verifications

```
$ python -c "import gemma4_agent; from gemma4_agent.router_v2 import route_v2"
(no output, exit 0)

$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65

$ python -m gemma4_agent.launcher status   # runs cleanly

$ python -m pytest test_router_v2.py -q
22 passed in 3.21s

$ python -m pytest gemma4_agent/ -q --tb=no
790 passed, 1 failed in 57.66s
```

La 1 falla restante (`test_planner_continuation.test_without_hint_short_reply_subset_empty`)
es pre-existente desde Sprint 3a; no introducida por 8a.

## Path para producción

Para activar v2 en el agente real:

1. Bootstrap (una sola vez por máquina):
   ```pwsh
   python scripts/bootstrap_e5_small.py
   ```
2. Para correr en SHADOW (recolectar comparativos sin riesgo):
   ```pwsh
   $env:GEMMA4_ROUTER_V2_SHADOW = "1"
   gemma4-launcher start
   ```
3. Después de Sprint 8c (con tunes + descriptions enriched):
   ```pwsh
   $env:GEMMA4_ROUTER_V2 = "1"
   gemma4-launcher start
   ```

## Lo que sigue

- **Sprint 8b:** reescribir las 65 tool descriptions a formato YAML
  con `purpose + example_queries (ES + EN)`. Sin esto, BM25 sigue
  ciego a "Netflix", "Daredevil", "investiga", etc. Los falsos
  positivos del smoke probe se resuelven aquí.
- **Sprint 8c:** correr el agente real una semana con
  `GEMMA4_ROUTER_V2_SHADOW=1`, exportar la distribución de
  `router_v2` events, calibrar finales: `CACHE_THETA`,
  `SMALLTALK_DELTA_THETA`, `FALLBACK_THETA`. Decidir activar v2 como
  default.

## Commits

```
76ee15e sprint8a.1: bootstrap script for e5-small ONNX router model
a0755b8 sprint8a.2: add router_v2.py with hybrid retrieval pipeline (default OFF)
26ef74f sprint8a.3: tests for router_v2 (skip integration tests if model absent)
ddee83b sprint8a.4: opt-in v2 routing via GEMMA4_ROUTER_V2 + shadow mode
<this commit>
```
