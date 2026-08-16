# Fine-tuning de Baxy — LLM + Encoder/Router (recetas reusables)

Copiado el 2026-06-14. Dos pipelines de FT que usábamos en Baxy. Te sirven como
plantilla para fine-tunear FunctionGemma (o lo que sea).

NO se copiaron los pesos base (`base_model/`, 25GB) ni los outputs (`out/`, 3GB):
se regeneran/descargan. Sí está el PIPELINE y el DATASET.

---

## 1) FT del LLM  →  `finetune_llm/`
Receta: **Unsloth QLoRA** sobre Gemma 4 E2B-it.

- `scripts/train_ft.py` — el entrenador. Config medida:
  - Base: `base_model/gemma-4-E2B-it` (bajar de unsloth/gemma-4-E2B-it, ungated).
  - **QLoRA 4-bit** (default): LoRA-16bit (~15GB bf16) NO entra en 16GB; QLoRA (~4GB) sí,
    calidad casi idéntica para SFT de un modelo chico.
  - LoRA r=16, alpha=32, dropout=0.05, target=all-linear.
  - **2 epochs** (medido: 3 epochs REGRESIONÓ el español, 2026-06-05).
  - MAX_SEQ=2048. `train_on_responses_only` (enmascara el prompt).
  - Datos: `curated/train_v3.jsonl` (con tool-results + grounding).
- `scripts/_merge_lora_standalone.py` — merge en PROCESO FRESCO (evita OOM).
- `scripts/quantize_gguf.py` — bf16 → imatrix → **Q4_K_M**.
- `scripts/build_v3.py`, `mask_v3.py`, `split_and_weight.py`, `schema.py` — construcción
  del dataset (sample_weight por ejemplo, split holdout, masking).
- `scripts/eval_ft_vs_baseline.py`, `eval_full_dimensions.py`, `boot_eval_model.py` — eval.
- `curated/` — el dataset: `train_v3.jsonl` (train final), `holdout.jsonl`, `curated.jsonl`,
  `conversation_*` (multilingüe), `synthetic_chains.jsonl`, etc. + variantes es-refined.

### GOTCHAS del FT del LLM (medidos — críticos)
1. **NUNCA `save_pretrained_merged`** — corrompe las capas custom de Gemma 4. Usar el merge
   PEFT `merge_and_unload` (en `_merge_lora_standalone.py`).
2. **Convertir a GGUF con `--outtype bf16`, NUNCA f16** (f16 degrada Gemma 4).
3. Pipeline GGUF: `convert_hf_to_gguf.py` (bf16) → `llama-imatrix` → `llama-quantize Q4_K_M`.
4. `import unsloth` segfault = xformers desalineado con torch (no el patch torchcodec).
5. Correr en el venv de Unsloth (`.venv_ft` en Baxy). OJO: ese venv hace **segfault** si lo
   usás para INFERENCIA standalone del encoder (usar python limpio para eso).

### Para FT de FunctionGemma (lo que vas a querer)
- Hay tutorial oficial: `unsloth.ai/docs/models/tutorials/functiongemma`.
- Base ungated: `unsloth/functiongemma-270m-it` o `-unsloth-bnb-4bit`.
- ~90-100 ejemplos por función (con variedad de fraseo) → 58%→85% (medido por Google/GDE).
- Formato propio: dataset de conversaciones {developer, user, model} + tools; el target es
  `<start_function_call>call:nombre{param:<escape>valor<escape>}<end_function_call>`.
- Hay un generador de dataset granular multilingüe de ejemplo en el repo de Baxy:
  `scripts/_diag/_build_fg_dataset.py` (lo dejé como referencia — adaptable).

---

## 2) FT del Encoder/Router  →  `router/scripts/`  (ya copiado en router/)
Receta: **fine-tune contrastivo** de un MiniLM-L12 (sentence-transformers).

- `train_router_encoder.py` — entrena el encoder con MultipleNegativesRankingLoss sobre
  `tool2vec_queries.jsonl` (query→tool) + corpus dev. 3 epochs, batch 64, seed 42.
  `--queries data/tool2vec_queries.lean.jsonl` para el set lean.
- `router_ft_pipeline.py` — tras entrenar el encoder, RECONSTRUYE todo lo dependiente:
  centroids (`router_tool2vec_build.py`), exemplars (`router_exemplar_build.py`),
  abstain head (`train_abstain_head.py`) y **tool_head (`train_tool_head.py`)** + eval.
- `router_eval.py` — recall holdout.

### GOTCHAS del FT del encoder (medidos)
1. **El `tool_head` DEBE reentrenarse junto al encoder.** Si cambiás el encoder y no lo
   reentrenás, sus márgenes colapsan (~0.13) → el router abstiene a TODO. El pipeline ya
   lo incluye (paso 2b). (Bug cazado 2026-06-14.)
2. Re-embeber el **exemplar store** con el nuevo encoder (si no, mezcla dos espacios y
   corrompe la abstención).
3. Seed fija (42) para artefacto regenerable bit-a-bit.
4. A/B medido: encoder entrenado sobre 67 vs 31 tools = **equivalente** (recall 0.9521).

---

## Resumen de qué hay en este repo
```
FunctionGemma/
├── model/                  ← GGUF de FunctionGemma (correr en llama.cpp)
├── tools/ + tool_schemas_*.json  ← tools de Baxy
├── router/                 ← encoder + router + route.py (narrowing) + scripts FT encoder
├── finetune_llm/           ← pipeline + dataset del FT del LLM (este doc)
├── README_RUNTIME.md / README_TOOLS.md / README_ROUTER.md / README_FINETUNE.md
```
