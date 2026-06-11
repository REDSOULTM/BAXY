# Router: reentreno del encoder con el corpus v3 (2026-06-11)

Objetivo: llevar el router a su techo con el corpus más completo disponible —
el dataset v3 del FT del LLM (6.905 filas auditadas, 67 tools × 6 idiomas,
1.526 labels corregidas, familias de fallos reales: pausa/battery-desktop/
identidad/garble).

## Receta (reproducible)

1. `dataset_finetune/scripts/to_router_corpus.py` ahora prefiere
   `train_v3.jsonl` y deriva `prev` del history multi-turno (un "a Luca"
   sin contexto enseñaría asociaciones falsas) →
   `gemma4_agent/data/router_corpus_curated_ft.jsonl`: **6.503 filas únicas**
   (4.432 con tool / 2.071 conversacionales / 1.526 corregidas).
2. `train_router_encoder.py` (seed 42, 3 epochs, 14.544 pares = sintéticos +
   dev-real + 4.614 FT-curated con holdout excluido por hash, 163 s en la
   4060 Ti) → dir TEMP AISLADO (`GEMMA4_ENCODER_OUT_DIR` a un subdir propio:
   el export ONNX escribe a `parent/router_encoder_onnx` y con el temp default
   pisaría el ONNX de prod ANTES de los gates) → swap.
3. `router_ft_pipeline.py`: re-embebe tool2vec centroids + exemplars (mezclar
   espacios corrompe el margen de abstención), re-entrena abstain head
   (threshold 0.68), evalúa.

## Resultados (todo medido, baseline congelado ANTES del swap)

| Harness | Baseline (encoder previo) | Stack v3 | Δ |
|---|---|---|---|
| Eval congelado dev (1.640) | recall 0.9832 / keep 0.9974 | idéntico — **misses byte-iguales** | 0 |
| Eval congelado holdout (421) | recall 0.9788 / keep 1.0000 | idéntico | 0 |
| Slices holdout (short/cont/multiling/idiomas) | 0.986/0.976/0.875/es 0.981 | idénticas | 0 |
| Canarios (63) | **47/63 = 74,6%** (preexistente, medido con rollback temporal) | 47/63 | 0 |
| Suite pytest routing | verde | verde | 0 |
| Probe fraseos de valor (10) | 10/10 | 10/10 | 0 |
| VIVO identidad 6 idiomas | 5/6 | 5/6 | 0 |
| VIVO "chi sei?" ×6 | 5/6 | **6/6** | ≥ |

**Veredicto: equivalencia conductual total + linaje mejor → se mantiene el
stack nuevo.** El router ya estaba en su techo MEDIBLE con la arquitectura
actual: el eval curado lo saturan las etapas keyword+exemplars+semántica en
conjunto, y el cuello real son los **16 canarios preexistentes** que fallan
IGUAL con ambos encoders ("que dia es hoy"→[], "cuanta RAM tengo"→[],
"cual es mi ip publica"→[] — gaps de etapas del planner/abstain, NO de
geometría del encoder). Ese es el siguiente frente si se quiere subir el
techo de verdad.

**Hipótesis declarada (sin prueba):** entrenar sobre la distribución
corregida v3 puede generalizar mejor a fraseos no vistos por los harneses;
ninguno de los benchmarks disponibles lo puede confirmar hoy.

## Rollback

Artefactos previos en `gemma4_agent/data/*.bak_pre_v3corpus_2026-06-11`
(encoder ST + ONNX + exemplars + centroids + abstain + meta + corpus).

---

# Sesión causa-raíz: los "16 canarios rotos" → 63/63 (2026-06-11)

Diagnóstico con descomposición por etapa (kw/exemplar/semántica/intent/
abstain/tool_head) + `sys.settrace` sobre `select_tool_names` para cazar la
línea exacta de cada mutación. CUATRO causas raíz, todas medidas:

| # | Causa | Evidencia | Fix |
|---|---|---|---|
| 1 | El harness corría el planner FRÍO: sin warmup, `semantic_router.status().model_loaded=False` → `scored=[]` → semántica apagada. Medía un router degradado que en prod no existe (el agente calienta al boot) | 47/63 frío vs 58/63 caliente, mismos artefactos | warmup en `router_canary_eval.py` (espejo de `router_eval._warm_router_for_eval`; tool_head importado de tools_pkg — el import de router_eval desde safety_pkg falla silencioso) |
| 2 | 3 labels anteriores a la política how-to/info del 2026-06-04 (bdcceda: "cómo elimino una carpeta" BORRÓ la carpeta → pregunta conceptual = el LLM responde, sin tools). Los canarios (2026-05-21) esperaban web\|knowledge para "que es una GPU/API/CPU" | cronología git + traza: L1508 `_is_howto_or_info_question` retira las tools por diseño | labels → `expect_empty` con nota de política |
| 3 | Guarda local-fact INCOMPLETA en el tool_head: `_suggest_tools` no apila web/knowledge si una tool local matcheó, pero el union del head (L1196) solo tenía la versión datetime → "cuanta RAM tengo" arrastraba `web` débil | settrace: `L1196 names ['system']→['system','web']` | guarda del head ampliada al set compartido `_LOCAL_FACT_TOOLS` |
| 4 | `contacts` fuera del set local-fact + flip frío/caliente de `wants_knowledge` (1ª llamada centroides sin cargar → False; 2ª → True): "tengo el numero de Juan" apilaba web/knowledge — la agenda es LOCAL | `plan_mission` mismo proceso: antes `['contacts']`, después de un select `['contacts','web','knowledge']` | `contacts` en `_LOCAL_FACT_TOOLS` |

**Resultado: canarios 47/63 → 63/63 (100%).** Anti-regresión: eval congelado
IDÉNTICO (dev 0.9832/keep 0.9974; holdout 0.9788/keep 1.0000), ruido dev
1.35→1.34 extra/turno (turnos ruidosos 58→56), suite routing 196 passed.

Gotcha de paso: `Set-Content -Encoding utf8` de PS 5.1 mete BOM y rompe el
json.loads del harness — re-escribir con python utf-8 sin BOM.
