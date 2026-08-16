# RESUME PROMPT — FG Tools-Reduce, loop abstención-E2E (2026-06-25)

> Leé esto + `ops/iteration_ledger.md` + `ops/TOOLS_REDUCE_STATE.md`.

## 🏆 CHAMPION ACTUAL (FINALIZADO + DEPLOYADO) = iter3
GGUF md5 **8fa2b441**. Canónico `model/functiongemma-tools-reduce-270m-it-Q8_0.gguf` = slot Baxy
`Probando Gemma 4/models/FunctionGemma/functiongemma-tools-reduce-270m-it-Q8_0.gguf` = iter3.
Backups: iter2 `-iter2-Q8_0.gguf` (md5 4c8e5a87), iter3 `-iter3-Q8_0.gguf`. Merged `archive/run_reduce3_5ep_merged`.

### iter3 DOMINA a iter2 (medido, FG aislado _ask, subset encoder real):
| métrica | iter2 | **iter3** |
|---|---|---|
| abstención-E2E total (eval_fg_abstain_e2e.py) | 76.3% | **89.5%** |
| KNOWLEDGE (preg→no_tool) | 25% | **100%** |
| ABSTAIN-removed | 81.2% | **87.5%** |
| CHITCHAT | 100% | 100% |
| CONTRAST-acción (anti over-refusal) | 90% | 90% |
| acción producción-fiel (eval_fg_reduced_e2e.py) | 95% | **97.5%** |
Fix que funcionó: hard-negatives con distractores REALES medidos (computer_use/filesystem/web_search,
de `discover_tempting_subsets.py`) + categoría knowledge→no_tool. Receta en `gen_reduced_abstain.py`.

## ⏳ CHALLENGER iter4 — datos LISTOS, train NO completó (reentrenar con máquina LIBRE)
- **Por qué:** los 4 fails de abstención de iter3 = email-FORWARD en fr/de/pt + 1 terminal-comando fr.
  iter4 agrega esos hard-negatives (gen_reduced_abstain v3, dataset 7872 YA construido, validate PASS, 0 fuga).
- **ESTADO: NO completó.** Murió 2 veces con MemoryError (bs4 y bs2) porque el agente de Baxy corría
  tests/retrains CONCURRENTES → RAM compartida a 0.0GB. El dataset y la receta están listos; falta SOLO
  reentrenar cuando la máquina esté libre.
- **QUÉ HACER (máquina libre, RAM >15GB):** rebuild NO hace falta (fg_train.jsonl ya es el de iter4).
  Verificá `python validate_dataset.py` (FG_CATALOG_DIR=reduced_catalog SLIM_SCHEMAS=1) → debe dar 7872/PASS.
  Entrená: `train_fg.py --full --lr 5e-5 --scheduler constant --epochs 5 --bs 2 --accum 8` (bs4 NO cabe).
  Luego, cuando exista `out_fg/merged-bf16` nuevo:
  ```powershell
  cd finetune_llm; $PY="...\.venv_ft\Scripts\python.exe"; $env:LLAMACPP_DIR="C:\llamacpp-src"
  cp -r out_fg/merged-bf16 archive/run_reduce4_5ep_merged
  & $PY quantize_fg.py --out functiongemma-tools-reduce-iter4   # -> model/...-iter4-Q8_0.gguf (NO pisa iter3)
  # desplegar iter4 al slot Baxy para evaluar (iter3 sigue respaldado en -iter3-Q8_0.gguf):
  cp model/functiongemma-tools-reduce-iter4-Q8_0.gguf "..\Probando Gemma 4\models\FunctionGemma\functiongemma-tools-reduce-270m-it-Q8_0.gguf"
  # matar server FG viejo (8082) para que rebootee con iter4:
  Get-Process llama-server -EA SilentlyContinue | Stop-Process -Force
  cd "..\Probando Gemma 4"
  $env:GEMMA4_FG_GPU="1"; ./.venv_router_train/Scripts/python.exe eval_fg_abstain_e2e.py
  ./.venv_router_train/Scripts/python.exe eval_fg_reduced_e2e.py
  ```
- **GATE para promover iter4**: abstención-E2E total y ABSTAIN-removed SUBEN vs iter3 (89.5%/87.5%) SIN
  bajar acción-producción (97.5%), knowledge (100%), chitchat, ni CONTRAST-acción (90%). Si pasa → ya está
  desplegado, actualizá canónico `cp model/...-iter4-Q8_0.gguf model/...-270m-it-Q8_0.gguf` + STATE + ledger.
  Si NO pasa → **restaurá iter3**: `cp model/...-iter3-Q8_0.gguf "..\Probando Gemma 4\models\FunctionGemma\functiongemma-tools-reduce-270m-it-Q8_0.gguf"`
  y registrá la lección (iter4 undertrained o email-forward no generalizó).

## RIESGOS / RESTRICCIONES MEDIDAS
- **RAM 31.8GB: full-FT bs4/accum4 NO cabe** (crashea con MemoryError/COMMITMENT_LIMIT). Usar SIEMPRE
  bs2/accum8 (~3:40h). El offload de gradientes Unsloth + double-buffering es el hog.
- Hubo un `scripts/train_router_encoder.py` (Baxy) que arrancó 02:45 y contendió GPU/RAM; lo maté
  (lanzamiento único, sin scheduler). Si reaparece y contiende, matarlo (memoria gpu-contention-kill).
- quantize_fg.py default pisa el canónico/deployado → SIEMPRE usar `--out <stem>` para challengers.

## ARTEFACTOS
- Held-out abstención: `Probando Gemma 4/eval_fg_abstain_e2e.py` (48 casos, 0 fuga, FG aislado + subset real).
- Eval acción: `Probando Gemma 4/eval_fg_reduced_e2e.py`. Descubrimiento: `discover_tempting_subsets.py` +
  `ops/tempting_subsets.json`. Receta negativos: `gen_reduced_abstain.py` (v3). Ledger: `ops/iteration_ledger.md`.
