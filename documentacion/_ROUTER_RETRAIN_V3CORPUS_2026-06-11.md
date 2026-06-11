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
