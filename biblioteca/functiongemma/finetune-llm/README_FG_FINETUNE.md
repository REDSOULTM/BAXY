# Fine-tune de FunctionGemma con TOOLS INDIVIDUALES — listo para correr

Adapta el dataset compuesto de Baxy (`train_v3.jsonl`) a los **tools descompuestos**
(individuales) y fine-tunea FunctionGemma-270M para que rutee bien. El modelo solo hace
function-calling (la conversación la hace otro LLM). Runtime objetivo: llama.cpp, VRAM ≤1.1GB.

## Estado: TODO LISTO, NO ENTRENADO (a pedido)
El pipeline está construido y validado de punta a punta con el `.venv_ft` de GPU
(`--dryrun` OK: device=cuda, ~7500 ejemplos, masking correcto). Falta solo ejecutar.

## Archivos
- `build_fg_trainset.py` — genera `curated/fg_train.jsonl` (~29.9k) y `fg_holdout.jsonl` (~1.9k).
  **Total ~31.787 ejemplos. Cobertura: 524/524 tools, 510 con ≥50 ejemplos, los 524 con ≥40**
  (cumple la recomendación de Google de ~50/función). Capas:
  - (A) routing desde curated.jsonl (acción recuperada cruzando train_v3 + fallback a la acción más común).
  - (B) granular con args limpios.
  - (C) cadenas multi-turno (encadenado).
  - (D) **hand-crafted: 23.384 ejemplos** escritos individualmente (no plantilla) por subagentes,
    multilingües (es/en/pt/fr/de/it), args válidos por schema, en `curated/hc/batch_*.jsonl`
    (specs en `curated/specs/`, guía en `curated/specs/INSTRUCTIONS.md`). Para regenerar/ampliar:
    editar/añadir triples {q,lang,tool,args} en esos .jsonl o en `curated/handcrafted.jsonl`.
  Cada fila lleva 8 tools (correcto + hermanos distractores) → enseña a desambiguar.
- VALIDADO: 85/85 lotes hand-crafted, 0 JSON/tool/args inválidos, 0 duplicados; 524/524 familias/tools
  con ejemplos; dryrun en GPU OK (28.753 efectivos, 100% supervisados, 1.142 descartados por len>3072).
- `train_fg.py` — LoRA (transformers+PEFT, sin Unsloth). r=16 α=32, 2 epochs, masking solo
  en el turno `model`. Importa `unsloth` primero (gotcha del venv) y descarta filas >3072 tok.
  Salida: `out_fg/lora` + `out_fg/merged-bf16`.
- `quantize_fg.py` — merged bf16 → GGUF bf16 → **Q8_0** (`../model/functiongemma-ft-270m-it-Q8_0.gguf`).
- `run_ft.ps1` — lanzador (1: dataset, 2: train+merge, 3: quantize) usando el venv de GPU.

## Cómo correr (cuando quieras)
```powershell
cd finetune_llm
powershell -ExecutionPolicy Bypass -File run_ft.ps1
```
O paso a paso con el venv:
```powershell
$PY = "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\.venv_ft\Scripts\python.exe"
& $PY build_fg_trainset.py
& $PY train_fg.py --smoke   # prueba rápida (80 ej); sacar --smoke para full
& $PY quantize_fg.py
```

## Entorno
- **No instalar nada**: usa `Probando Gemma 4/.venv_ft` (torch 2.7.0+cu126, transformers 5.5,
  peft, trl, RTX 4060 Ti). 270M en LoRA bf16 entra de sobra; no hace falta QLoRA/bitsandbytes.
- `quantize_fg.py` necesita `convert_hf_to_gguf.py` de llama.cpp. Si falta:
  `git clone --depth 1 https://github.com/ggml-org/llama.cpp C:\llamacpp-src` y
  `$env:LLAMACPP_DIR="C:\llamacpp-src"`.

## VRAM ≤1.1GB (objetivo)
El GGUF Q8 de 270M ≈ 290MB de pesos. Con el router narrowing (~8 tools) basta `-c 4096`:
KV+compute quedan chicos → total muy por debajo de 1.1GB (el base Q8_K_XL a 32K ya daba ~1.1GB).
```
C:\llamacpp-cuda\bin\llama-server.exe -m model\functiongemma-ft-270m-it-Q8_0.gguf ^
  --port 8082 --jinja -ngl 99 -c 4096 --no-webui
```

## Encadenado (multi-step) — habilitado por FT
FunctionGemma base NO viene entrenado para encadenar (Google: solo single/parallel; la doc
oficial recomienda **fine-tuning** para multi-step). Lo habilitamos así:
- **Datos**: ~359 cadenas multi-turno (`from_chains` en build_fg_trainset.py) en el formato
  nativo del template: `model(call_1) → tool(<start_function_response>…) → model(call_2) → …`.
  Fuente: filas multistep de train_v3 (acciones reales) + synthetic_chains/ + multistep/.
- **Masking**: `train_fg.py` supervisa la pérdida en TODOS los turnos `model` (no solo el
  último) — verificado: una cadena de 2 pasos da 2 segmentos supervisados. Sin esto, el
  modelo no aprende a emitir la 2ª call tras ver el resultado.
- **Runtime**: `fg_chain_client.py` (raíz) — bucle de orquestación contra llama.cpp:
  renderiza el prompt con el template, `stop=["<end_function_call>","<end_of_turn>"]`,
  parsea la call, ejecuta, devuelve el resultado como turno `tool`, y pide la siguiente.
  Para cuando el modelo no emite más calls (o al tope de pasos).

## Integración (post-train)
1. Router (`fg_router_ft.py`) narrowea query → ~8 tools individuales.
2. Esos tools → llama.cpp (rol `developer`, `temperature=1.0 top_k=64 top_p=0.95`,
   `stop=["<end_function_call>"]`). El call sale en `content`: regexear
   `<start_function_call>call:NOMBRE{p:<escape>v<escape>}<end_function_call>` (ver README_RUNTIME).
3. Handlers ejecutan; otro LLM conversa.

## Mejoras futuras del dataset
- Extraer valores de args desde `user_text` para los tools de la capa A (hoy se saltan los
  que necesitan valor; los cubre la capa B). Subiría cobertura de args del long-tail.
- ~90-100 ej/función (Google) para el set de tools que más se usen.
