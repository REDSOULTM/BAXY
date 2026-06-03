# Componentes del router

> Cada módulo de código y cada artefacto de datos, con su rol, sus entradas y
> cómo se regenera. Todo es REPRODUCIBLE: ningún artefacto sin su receta.

---

## Módulos de código (`gemma4_agent/routing/`)

| Archivo | LOC | Rol |
|---------|----:|-----|
| [`router.py`](../../gemma4_agent/routing/router.py) | 88 | **Entry point único.** Re-exporta toda la API pública. Importás `router` y tenés todo. |
| [`planner.py`](../../gemma4_agent/routing/planner.py) | 1618 | **El orquestador (cerebro).** `select_tool_names()` corre las 6 capas. `plan_mission()` parte la frase en pasos. Aquí viven el cap, los collapses, los rescates. |
| [`intent_router.py`](../../gemma4_agent/routing/intent_router.py) | 750 | **Los 5 centroides de intención** (info/action/chitchat/selfref/meta). `wants_knowledge()`, `is_conversational()`. 100% semántico, anchors multilingües. |
| [`semantic_router.py`](../../gemma4_agent/routing/semantic_router.py) | 526 | **Retrieval.** Carga el encoder FT, las `TOOL_DESCRIPTIONS`, los centroides Tool2Vec. `suggest_tools_scored()`. `enroll_mcp_tools()` para MCPs. |
| [`exemplar_router.py`](../../gemma4_agent/routing/exemplar_router.py) | 192 | **Memoria de casos.** Nearest-neighbor sobre ejemplos históricos etiquetados. Voto ponderado + abstención por margen (S3c). |
| [`command_splitter.py`](../../gemma4_agent/routing/command_splitter.py) | 640 | Parte cadenas imperativas ("abrí X, escribí Y, apretá Z") en pasos. Techo verificado = 3 pasos. |
| [`context_router.py`](../../gemma4_agent/routing/context_router.py) | 206 | Decide cuánto historial mandar al LLM por turno (multilingüe por embeddings). Gate `GEMMA4_CONTEXT_ROUTER`. |
| [`deictic_detector.py`](../../gemma4_agent/routing/deictic_detector.py) | 183 | Detecta deícticos ("abrilo", "subilo") e inyecta el referente del turno previo. Gate `GEMMA4_DEICTIC`. |
| [`reranker.py`](../../gemma4_agent/routing/reranker.py) | 98 | Cross-encoder condicional. Rescata queries cortas/ambiguas en la banda "vacío-pero-no-charla". Gate `GEMMA4_RERANKER`. |

Modelos auxiliares fuera de `routing/`:
- [`gemma4_agent/safety_pkg/abstain_head.py`](../../gemma4_agent/safety_pkg/abstain_head.py) — el head de abstención NO-TOOL (forward = dot product numpy).
- [`gemma4_agent/tools_pkg/tool_head.py`](../../gemma4_agent/tools_pkg/tool_head.py) — el per-tool logit head.

---

## Artefactos de datos (`gemma4_agent/data/`)

| Artefacto | Tamaño | Qué es | Se regenera con |
|-----------|-------:|--------|-----------------|
| `router_eval_corpus.curated.jsonl` | 312 KB | **Corpus de eval curado** (1733 filas, labels hand-authored por Opus). El ground-truth principal. | `scripts/router_corpus_curate.py` (labels en `router_corpus_labels.py`) |
| `router_corpus_real_logs.jsonl` | 253 KB | **Corpus de LOGS REALES** del usuario (1071 pares query→tool de `traces.jsonl`). La verdad de campo. | `scripts/router_corpus_from_logs.py` |
| `router_exemplars.npz` | 2.5 MB | Ejemplos históricos + embeddings para el exemplar router (= las 1733 filas curadas). | `scripts/router_exemplar_build.py` |
| `tool2vec_queries.jsonl` | 208 KB | 3573 pares sintéticos multilingües (query→tool) para entrenar el encoder. | `scripts/router_tool2vec_generate.py` |
| `tool2vec_centroids.npz` | 99 KB | Centroides Tool2Vec por tool (el α=0.6 del retrieval). | `scripts/router_tool2vec_build.py` |
| `abstain_head.json` | 879 B | Pesos de la regresión logística de abstención (plano, sin pickle). | `scripts/train_abstain_head.py` |
| `tool_head.json` | 494 KB | Pesos del per-tool logit head (62 tools, cada una su umbral). | `scripts/train_tool_head.py` |
| `router_encoder_ft/` | dir | El encoder MiniLM fine-tuneado sobre la distribución propia. | `scripts/train_router_encoder.py` (CUDA, ~12h) |
| `router_encoder_meta.json` | 239 B | Metadata del encoder FT (tool descriptions snapshot). | (output del training) |
| `router_prev_map.json` | 78 KB | Mapa query→turno-previo (reconstruido del log ordenado) para que `--use-prev`/`--inherit` resuelvan deícticos. | snippet en el sprint del corpus |
| `router_canaries.jsonl` | 5.6 KB | Canarios: queries con la tool que NUNCA debe perderse (regresión dura). | manual |

**Regla del proyecto:** ningún artefacto sin su receta versionada. Si bajás algo
de internet, dejá el script de descarga, no solo el archivo.

---

## Las 3 "cabezas" entrenadas (cómo se relacionan)

```
                 encoder FT (router_encoder_ft/)
                       │  cambia la geometría de TODOS los vectores
        ┌──────────────┼──────────────┐
        ▼              ▼               ▼
  Tool2Vec        abstain_head     tool_head
  centroids       (features del     (logit por tool
  (re-embed)       encoder)          sobre embeddings)
```

**Importante:** si reentrenás el encoder FT, hay que re-derivar TODO lo demás con
ese encoder (su geometría cambió). Eso lo hace `scripts/router_ft_pipeline.py`
en una sola corrida. NO mezclar un encoder nuevo con cabezas viejas.

---

## Las capas del runtime vs. el training

| Componente runtime | Se entrena con | Idiomas que ve |
|--------------------|----------------|----------------|
| `intent_router` (centroides) | anchors hardcodeados en el .py | multilingüe (anchors en 6 idiomas) |
| `semantic_router` (descripciones) | `TOOL_DESCRIPTIONS` en el .py | multilingüe (se enriquecen a mano) |
| `abstain_head` | corpus curado (dev split) | **99% ES** ← causa de la fuga DE |
| `tool_head` | embeddings del corpus + tool2vec | mixto |
| `encoder FT` | tool2vec (3573 pares multilingües) + corpus dev | multilingüe pero base débil en DE |

Este cuadro explica el límite del alemán: el `abstain_head` se entrena casi solo
con español, y opera sobre features de un encoder base con cobertura DE débil.
Ver [06_PENDIENTE_Y_NO_FORZADO.md](06_PENDIENTE_Y_NO_FORZADO.md).

---

## Scripts (`scripts/`)

### Evaluación
- `router_eval.py` — el harness principal. Recall + NO-TOOL keep + PRECISIÓN.
- `router_canary_eval.py` — corre los canarios (regresión dura).
- `router_diag.py` — diagnóstico de una query (qué dispara cada capa).
- `_live_verify_router_s3.py` — verificación EN VIVO de los fixes S3 contra el LLM real.

### Construcción de corpus
- `router_corpus_from_logs.py` — corpus desde los logs reales del usuario.
- `router_corpus_build.py` + `router_corpus_labels.py` — corpus curado (carter + logs).
- `router_corpus_curate.py` — aplica los labels hand-authored al corpus curado.

### Construcción de artefactos
- `router_exemplar_build.py` — el .npz de exemplars.
- `router_tool2vec_generate.py` / `router_tool2vec_build.py` — pares + centroides.

### Training
- `train_abstain_head.py` — el head de abstención (rápido, CPU).
- `train_tool_head.py` — el per-tool head (rápido, CPU).
- `train_router_encoder.py` — el encoder FT (CUDA, ~12h).
- `router_ft_pipeline.py` — re-deriva TODO tras un encoder nuevo.
- `setup_router_train_venv.ps1` — crea el venv `.venv_router_train` (3.11 + CUDA).
