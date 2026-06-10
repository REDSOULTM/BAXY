# Misión: dejar a Baxy perfecto — HANDOFF para la sesión de las 04:35

## Objetivo
Probar a Baxy/Carter EN VIVO (LLM real levantado) con prompts del dataset de
finetuning, cazar fallas de CALIDAD / LATENCIA / otros, encontrar causas raíz y
arreglarlas.

## El script ya está hecho y validado: `scripts/_diag/_mission_eval.py`
- Reusa la maquinaria probada de `_diag_finetune_dataset_eval.py` (boot del LLM
  real, mock SEGURO de ejecución física — NO toca la PC, run_content = la UI).
- Muestreo GARANTIZADO: ≥18 categorías × ≥10 prompts (validado: hay 27 categorías
  con ≥10 ejemplos en `dataset_finetune/curated/curated.jsonl`; tomará ~220 prompts).
- Detectores: tool_mismatch, empty_reply, special_token_leak, old_name_gemma,
  footer/meta leak, ocr_echo, tool_call_leaked, lang_drift, reply_too_long,
  many_passes(≥4), slow(>6s).
- Salidas: `_mission_eval_results.jsonl` (crudo por prompt) +
  `documentacion/_MISSION_EVAL_REPORT.md` (agregado por tipo y por categoría).

## Pasos a ejecutar en la sesión
1. Cerrar cualquier asistente/server viejo que tenga el encoder/LLM (si bloquea).
2. Correr: `python scripts/_diag/_mission_eval.py` (en background, ~15-25 min).
   - Levanta el llama-server solo. Va imprimiendo progreso + ETA.
3. Leer `documentacion/_MISSION_EVAL_REPORT.md`: priorizar las categorías y tipos
   de falla con mayor %.
4. Por cada cluster de falla: reproducir el prompt en vivo, diagnosticar la CAUSA
   RAÍZ (no el síntoma), arreglar, re-medir el cluster.
5. Suite verde + commit a AMBOS repos (origin+asistia, main+Dev, 4 refs).

## Restricciones (de siempre)
- NO tocar el workstream vision_input (gestos/cámara, en desarrollo).
- Mock seguro: el script no ejecuta efectos físicos; el LLM sí corre real (latencia
  medida = real). Si algo físico necesita validación, queda para el usuario.
- Medir antes de declarar éxito; causa raíz antes de parchear.

## Tuning por env (si hace falta)
- `GEMMA4_MISSION_CATS=18` `GEMMA4_MISSION_PER_CAT=10` `GEMMA4_MISSION_SLOW_S=6.0`
  `GEMMA4_MISSION_MAXLEN=600`
