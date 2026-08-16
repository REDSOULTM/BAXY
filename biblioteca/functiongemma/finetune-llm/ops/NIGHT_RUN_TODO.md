# NIGHT RUN — TODO

## EN CURSO
- [ ] Monitorear training `bqya22m9e` (train_run.log) hasta completar 1539 pasos + merge.

## AL TERMINAR EL TRAINING (run actual)
- [ ] Verificar que existan `out_fg/lora/adapter_model.safetensors` y `out_fg/merged-bf16/model.safetensors`.
- [ ] **ARCHIVAR** el adapter+merged en `archive/run1-<ts>/` ANTES de cualquier relanzamiento (train_fg.py limpia out_fg).
- [ ] EVAL del merged (con sampling oficial temp=1.0/topk64/topp95, NO solo greedy):
  - [ ] Holdout: precisión de tool correcta, args válidos, 0 tools inventadas, 0 JSON malo.
  - [ ] `no_tool`: chitchat/conocimiento/ambiguo → no_tool ; tool-intent → NO no_tool.
  - [ ] Multilingüe es/en/pt/fr/de/it.
  - [ ] Tools hermanas (get/set, connect/disconnect, create/list/delete).
  - [ ] Cadenas multi-step (alimentar tool_result → siguiente call).
  - [ ] Adversariales (ambiguos, sin args, valores raros).
- [ ] Comparar vs baseline (eval_ft_vs_baseline.py / _headtohead) si aplica.
- [ ] Si EVAL bien → marcar como CHAMPION → quantize_fg.py → validar GGUF.
- [ ] Si EVAL flojo → diagnosticar fallas, generar datos focalizados, rebuild, dryrun, reentrenar.

## SEGURIDAD ANTES DE RELANZAR
- [ ] Añadir/usar `--no-clean` o `--resume` en train_fg.py para no borrar checkpoints (HECHO? ver train_fg.py).
- [ ] Archivar artefactos buenos antes de cualquier run nuevo.

## MEJORAS CANDIDATAS (solo si eval lo justifica)
- [ ] Epoch 2 (si loss/eval sigue mejorando, sin degradar no_tool/args).
- [ ] Subir MAX_SEQ a 3072/4096 para recuperar los ~5k ejemplos descartados (270M aguanta; vigilar OOM/velocidad).
- [ ] Rebalancear idiomas si multilingüe flojea.
- [ ] Datos focalizados para tools/casos que fallen en eval.

## INFRA / CONTINUIDAD
- [ ] Mantener NIGHT_RUN_STATE.md y RESUME_PROMPT.md actualizados tras cada hito.
- [ ] Recordatorios de continuación activos.
