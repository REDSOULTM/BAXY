# Router + Encoder de Baxy — bundle para FunctionGemma

Copiado desde Baxy el 2026-06-14. El router toma una query y devuelve los **top-k tools
relevantes** — justo lo que FunctionGemma necesita para no recibir 31 tools de golpe
(que le da HTTP 400 / lo hace rechazar).

## Qué hay
- `routing/` — código del router. El núcleo es **`semantic_router.py`** (autónomo:
  encoder MiniLM fine-tuneado + centroids Tool2Vec; solo necesita sentence-transformers
  + numpy). El resto (planner.py, exemplar_router.py, intent_router.py, command_splitter.py)
  es el stack completo de Baxy — más potente pero con imports relativos a gemma4_agent.
- `data/router_encoder_ft/` — el **encoder fine-tuneado** (MiniLM-L12, 384-dim, 470MB).
  Es el encoder-31 (entrenado sobre el set lean de 31 tools).
- `data/tool2vec_centroids.npz` — centroides por-tool (lo que usa `suggest_tools_scored`).
- `data/router_exemplars.npz`, `abstain_head.json`, `tool_head.json` — artefactos del
  planner completo (exemplar memory, cabeza de abstención, cabeza per-tool).
- `heads/tool_head.py`, `heads/abstain_head.py` — código de las cabezas entrenadas.
- `scripts/` — entrenar/reconstruir todo: `train_router_encoder.py` (FT del encoder),
  `router_ft_pipeline.py` (rebuild centroids+exemplars+abstain+tool_head+eval),
  `router_tool2vec_build.py`, `router_exemplar_build.py`, `train_abstain_head.py`,
  `train_tool_head.py`, `router_eval.py`.
- `data/tool2vec_queries.jsonl` (+ `.lean.jsonl`) — queries sintéticas query→tool.
- `data/router_eval_corpus.curated.jsonl`, `router_corpus_curated_ft.jsonl` — corpus
  real curado para eval/FT.
- `route.py` — wrapper STANDALONE listo para usar (query → top-k tools). PROBADO ✓.

## Uso inmediato (PROBADO)
```bash
pip install sentence-transformers numpy
python route.py "qué hora es" --k 5
# -> [{"tool":"system","score":0.6272}, {"tool":"notification",...}, ...]
```
```python
from route import route
top = route("pon música de bad bunny", k=6)   # [(tool, score), ...]
```

⚠️ **Usá un Python LIMPIO** (con sentence-transformers + numpy). NO uses un venv con
Unsloth instalado — Unsloth parchea torch y hace **segfault** al cargar el encoder
standalone (medido). El Python normal del sistema anda.

## Integración con FunctionGemma (el patrón que buscás)
```python
import json
from route import route
schemas = {t["function"]["name"]: t for t in json.load(open("../tool_schemas_lean.json"))}
def tools_for(query, k=6):
    names = [t for t,_ in route(query, k=k)]
    return [schemas[n] for n in names if n in schemas]   # solo los relevantes
# luego: body["tools"] = tools_for(user_query)  -> a FunctionGemma (rol developer, ctx 32K, stop=<end_function_call>)
```
Esto resuelve el overflow: FunctionGemma recibe ~6 tools en vez de 31.

## Qué corre standalone vs qué no
- ✅ `semantic_router.suggest_tools_scored(query, k)` (vía `route.py`) — autónomo.
- ⚠️ `planner.select_tool_names(...)` (el router completo con exemplar+abstain+tool_head):
  más preciso, pero `planner.py`/`exemplar_router.py` importan de `gemma4_agent` (p.ej.
  `from ..tools_pkg.tool_head import`, `from ..safety_pkg.abstain_head import`). Para
  usarlo hay que reescribir esos imports a `heads/`. Para FunctionGemma, `suggest_tools_scored`
  alcanza.

## Reconstruir / re-finetunear
El encoder y los artefactos se regeneran desde `scripts/` + `data/`. Correr en un venv
con torch+sentence-transformers (NO el de Unsloth para inferencia). El encoder se entrena
con `train_router_encoder.py --queries data/tool2vec_queries.lean.jsonl`; luego
`router_ft_pipeline.py` reconstruye centroids/exemplars/abstain/tool_head y mide holdout.
GOTCHA medido: el `tool_head` DEBE reentrenarse junto al encoder (si no, sus márgenes
colapsan ~0.13 y el router abstiene a todo).

## Datos del encoder (medido)
- A/B encoder-67 vs encoder-31 (lean): **equivalente**, holdout TOOL RECALL 0.9521 ambos.
- Es MiniLM-L12 384-dim, CPU-friendly (~120MB en RAM al cargar como SentenceTransformer).
