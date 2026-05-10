# harness_carter540 — Gemma 4 puro vs 540 cases

Testbed standalone para comparar quants de Gemma 4 sobre los 540 casos
oficiales del bench Carter, **sin dependencias del repo Carter**.

## Estructura

```
harness_carter540/
├── tool_schemas.json    # 60 tool schemas (snapshot del catalogo Carter)
├── stubs.py             # 60 stub impls deterministas
├── tests_540.md         # 540 casos oficiales (copiado del repo)
├── tests.py             # Loader del .md
├── system_prompt.py     # SYSTEM_PROMPT v3 sin agent loop
├── auditor.py           # PASS/FAIL por caso
├── run_bench.py         # Runner single-model standalone
├── run_all_models.py    # Orquestador multi-modelo
├── generate_stubs.py    # Validador stubs vs schemas
└── results/             # Salida (JSON por modelo + comparativa)
```

## Filosofía

- **Stubs deterministas**: cada tool devuelve un valor fijo plausible.
  Esto mide al MODELO (tool selection + args), NO al SO.
- **Sin agent loop**: prompt + LLM + tools + 1-4 turnos max. Carter
  agent.py NO se importa.
- **Auditor conservador**: PASS sólo si el modelo emite la tool correcta
  Y la latencia entra en budget. Honest replies (Pattern G dossier 14)
  cuentan como PASS.

## Uso

1. Descargar el quant deseado a `../models/E4B/`.
2. Levantar llama-server:
   ```
   llama-server.exe -m ../models/E4B/<quant>.gguf --jinja -ngl 99 -c 16384 \
       --parallel 1 --ctx-checkpoints 1 --flash-attn on \
       --cache-type-k f16 --cache-type-v f16 --no-context-shift \
       --reasoning off --reasoning-budget 0
   ```
3. Run single model:
   ```
   python run_bench.py --model E4B-Q4_K_M --output results/Q4_K_M_run.json
   ```
4. O run TODOS los modelos:
   ```
   python run_all_models.py
   ```

## Modelos comparados

| Quant | Tamaño | VRAM cargado | Bench externo (60 tests) |
|-------|--------|---|---|
| UD-IQ2_M | 3.55 GB | ~5.1 GB | 91.6% |
| Q4_K_M | 4.98 GB | ~6.1 GB | 93.3% |
| Q5_K_M | 5.48 GB | ~6.6 GB | 91.6% |
| Q6_K | 7.07 GB | ~7.1 GB | 95.0% |
| Q8_0 | 8.19 GB | ~8.2 GB | 91.6% |

## Sources

- [Gemma 4 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Unsloth Gemma 4 GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF)
- [llama.cpp issue #21690](https://github.com/ggml-org/llama.cpp/issues/21690)
- `../REPORTE_EXTENDIDO.md` (60-test bench resultados)
- `../../Carter OS AI/investigacionnecesaria/audit_qwen3/14_OPUS_DOSSIER_PATRONES_A_P.md`
