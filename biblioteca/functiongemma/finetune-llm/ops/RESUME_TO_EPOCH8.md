# Cómo seguir entrenando run6 hasta epoch 8 (o más)

run6 = full fine-tuning, 5 epochs, lr 5e-5, scheduler constant, slim schemas, seq 1280.
Guarda checkpoints CON estado del optimizer (resumibles) en `out_fg/ckpt/checkpoint-N`
cada ~930 pasos (save_total_limit=4 → quedan los últimos 4).

## IMPORTANTE: preservar el checkpoint final
Los runs nuevos de `train_fg.py` BORRAN `out_fg/` al arrancar (salvo `--no-clean`).
Tras run6 se archiva el checkpoint final en `archive/run6_ckpt_final/` (full model + optimizer.pt
+ scheduler.pt + trainer_state.json). Cada checkpoint full-FT pesa ~2.7GB (modelo + optimizer fp32).

## Comando para continuar a epoch 8
```powershell
cd "C:\Users\usuario\Desktop\ETC\Programacion\FunctionGemma\finetune_llm"
$PY="C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\.venv_ft\Scripts\python.exe"
# 1) si el checkpoint está archivado, copialo de vuelta a out_fg/ckpt/
#    (o apuntá --resume directo al path del archive)
# 2) continuar: MISMA config (--full, lr, scheduler), subiendo --epochs a 8, con --no-clean
& $PY -u train_fg.py --full --lr 5e-5 --scheduler constant --epochs 8 --no-clean `
      --resume "archive\run6_ckpt_final\checkpoint-<N>" > train_run.log 2>&1
```
El Trainer lee el global_step del checkpoint y continúa desde ahí hasta completar 8 epochs
(no re-entrena lo ya hecho). Al terminar, mergea a `out_fg/merged-bf16` → `quantize_fg.py`.

## Notas
- Usar SIEMPRE `--no-clean` al resumir (si no, borra el checkpoint antes de leerlo).
- El sampler es determinista (length-grouped + seed 42) → el resume saltea los batches correctos.
- Si querés MÁS de 8, subí `--epochs`. El scheduler constant hace el resume trivial (lr fijo).
- Para evaluar un checkpoint intermedio sin seguir: `eval_night.py --model out_fg/ckpt/checkpoint-N`
  (o copiar el checkpoint y cargarlo como modelo full).
