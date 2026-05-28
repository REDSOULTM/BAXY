# `gemma4_agent/data/` — artefactos de datos y modelos

Este directorio aloja datasets, modelos pre-computados y configuraciones
que el runtime necesita. Cada archivo no-text DEBE tener una receta de
generación documentada acá — el audit `architecture_audit_2026_05_27`
(§8 "Reproducibilidad como requisito, no lujo") lo flaggeó.

## Archivos pre-computados (`.npz`)

### `router_exemplars.npz`

Embeddings de exemplars del router para clasificación por proximidad.
Producido por:

```bash
python scripts/router_exemplar_build.py
```

Input: corpus curado en `gemma4_agent/data/router_eval_corpus.jsonl`.
Output: `data/router_exemplars.npz` con shape (N, D) donde N=número de
exemplars y D=384 (dimensión del encoder multilingüe).

Se regenera cuando:
- Se modifica el corpus
- Se cambia el encoder backend
- Aparece un drift en evals del router (`scripts/router_eval.py`)

### `tool2vec_centroids.npz`

Centroides per-tool del router semántico (TOOL2VEC). Mapea cada nombre
de tool a un vector promedio de sus exemplars.

```bash
python scripts/router_tool2vec_build.py
```

Input: corpus + lista de tools de `tool_schemas.py`.
Output: `data/tool2vec_centroids.npz` (dict-like: {tool_name: vector}).

Se regenera cuando se agrega/elimina una tool del registry.

## Configuraciones (`.json`, `.yaml`)

- `state.json` — estado vivo del agente (resources, checkpoints,
  pending_intents). Se modifica en runtime; NO regenerable, es state.
- `routes/*.yaml` — overrides de routing del router. Editables a mano.
- `tool_aliases.json` — aliases del LLM (`gmail` → `email`). Editable.

## Datasets

- `router_eval_corpus.jsonl` — corpus curado de evaluación del router
  (~3,300 entradas). Se editan con `scripts/router_corpus_curate.py`.
- `router_eval_corpus.curated.jsonl` — variante curada del corpus.
- `router_canaries.jsonl` — canarios para detección de regresión rápida.
- `tool2vec_queries.jsonl` — queries para construir centroides.
- `router_prev_map.json` — mapa de tools previas para continuación.
- `router_encoder_meta.json` — metadata del encoder fine-tuned.
- `abstain_head.json` — pesos de la cabeza de abstención del router.
- `tool_head.json` — pesos de la cabeza per-tool del router.
- `memory.json` — store de memoria persistente del agente.
- `state.json` — estado vivo (resources, checkpoints). MUTABLE en runtime.

## Política de reproducibilidad

Para cualquier `.npz` / `.bin` / `.pkl` nuevo que entre acá:
1. Documentar la receta en este README.
2. El script de generación va en `scripts/` con prefijo del área.
3. Si el archivo es grande (>10 MB), considerar `.gitignore` + script de
   generación on-demand en lugar de versionar.
