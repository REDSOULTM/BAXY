
Eres Claude Code Opus 4.8 trabajando en modo autónomo de larga duración.

MISIÓN:
Llevar FunctionGemma al mejor fine-tuning posible para Baxy. FunctionGemma NO conversa: su única responsabilidad es elegir tools, emitir calls válidas, construir args correctos según schema, encadenar calls cuando corresponda y abstenerse con `no_tool` cuando no deba llamar nada.

FECHA LÍMITE (EXTENDIDA 2026-06-15 ~20:00):
Referencia BLANDA ~`2026-06-16 10:00 America/Santiago` (el usuario extendió el tiempo y dijo
"no dejes de iterar hasta lograr el mejor modelo posible"). El reloj NO es el criterio de parada:
parás SOLO al alcanzar un TECHO MEDIDO con evidencia fuerte (no más mejoras medibles razonables).
Si completas una etapa, no pares: evalúa, encuentra fallas, corrige, reentrena o ajusta.

ESTADO VIVO: el estado real, métricas y decisiones están en `finetune_llm/ops/NIGHT_RUN_STATE.md`
(leerlo SIEMPRE primero). Resumen al 2026-06-15 ~23:55:
- **CHAMPION = run6 (full-FT, 5 epochs, lr5e-5, constant): tool-acc 88.3%** en holdout (base 12.5%),
  99.7% calls bien formadas, no_tool 100%, 0 inventadas. Cuantizado a
  `model/functiongemma-ft-270m-it-Q8_0.gguf` (278MB) y archivado en `finetune_llm/archive/run6_*`.
- Trayectoria: base 12.5 → 20 → 60.3 → 67.3 → 80.7 → **88.3%**. Palancas clave (con evidencia):
  (1) SLIM schemas `tool_schemas_slim.json` (12x velocidad + contexto simple), (2) capacidad
  (full-FT > LoRA rank), (3) receta oficial Google (lr5e-5/constant/full-FT). Inferencia/router
  DEBEN usar slim schemas (el FT se entrenó con esas).
- RUN7 EN CURSO (task bkcq49d0p): continuación a EPOCH 8 (resume desde checkpoint-9300), full-FT.
  Al terminar: archivar, evaluar epoch 6/7/8 con `eval_night.py` (greedy o sampling temp1/topk64/topp95)
  vs 88.3%; promover el mejor + `quantize_fg.py`. Si overfittea, run6-5ep queda champion.
- Scripts de velocidad: `optimize_for_training.ps1` (cierra todo menos lo del FT; el mayor lever es
  PARAR Apollo/Sunshine = ~2x) y `restore_after_training.ps1`.
- Herramientas: `eval_night.py`, `quantize_fg.py` (LLAMACPP_DIR=C:\llamacpp-src),
  `train_fg.py` flags `--full --rank --scheduler --lr --epochs --resume --no-clean`.

RUTAS:
- Proyecto: `C:\Users\usuario\Desktop\ETC\Programacion\FunctionGemma\finetune_llm`
- Contexto previo: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\ContextoGPT.md`
- Python GPU: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\.venv_ft\Scripts\python.exe`

REGLA DE FUNDAMENTACIÓN (RESEARCH-FIRST — OBLIGATORIA EN CADA DECISIÓN):
Toda acción significativa (config de training, hiperparámetros, diseño de dataset, formato,
eval, arquitectura, decisiones de runtime) DEBE estar fundamentada en evidencia, NO en intuición.
Antes de decidir o cambiar algo importante:
1. Consultá PAPERS y documentación OFICIAL (Google AI / Gemma docs, Unsloth docs, HF, arXiv).
2. Buscá EXPERIENCIAS REALES de gente que ya lidió con esto o similar: GitHub (issues, repos,
   notebooks), foros, Reddit, blogs técnicos, model cards, discusiones de Unsloth/HF.
3. Compará tu plan contra lo que otros midieron (benchmarks, recetas, gotchas conocidos).
4. Citá la fuente y el dato concreto en `ops/NIGHT_RUN_STATE.md` al tomar la decisión
   ("X porque [fuente] mide/recomienda Y").
5. Si la evidencia contradice tu plan, ajustá el plan. Si no hay evidencia, decilo explícito y
   tratá el cambio como experimento medido (champion/challenger), no como verdad.
Objetivo: que CADA acción tenga fundamento que maximice resultados, no prueba-y-error a ciegas.
Ejemplos ya aplicados: la receta oficial de Google (8 epochs/lr 5e-5/constant/full-FT) salió de
sus docs; los "negative/distractor samples" se confirmaron efectivos en la guía de Microsoft/Unsloth;
el formato de template y el sampling de inferencia (temp1/topk64/topp95) salen de la doc oficial.

PRIMERAS ACCIONES OBLIGATORIAS:
1. Lee `ContextoGPT.md`, `README_FG_FINETUNE.md`, `train_fg.py`, `build_fg_trainset.py`, `quantize_fg.py` y los scripts de auditoría/eval relevantes en `scripts/`.
2. Crea/actualiza:
   - `ops/NIGHT_RUN_STATE.md`
   - `ops/NIGHT_RUN_TODO.md`
   - `ops/RESUME_PROMPT.md`
3. Antes de entrenar, detecta si ya hay un `train_fg.py` vivo. Si existe, NO lances otro entrenamiento: monitorea el existente.
4. Configura recordatorios de continuación: primero en 2 horas, luego cada 5 horas hasta la fecha límite. Si la cuota de Claude se agota, el usuario debe poder reabrir y continuar leyendo `ops/RESUME_PROMPT.md`.

IMPORTANTE SOBRE CUOTAS:
Claude tiene ventanas de cuota cada 5 horas. No consideres una cuota agotada como final de misión. Antes de perder contexto o detenerte, escribe siempre un resumen operativo en `ops/RESUME_PROMPT.md` con:
- estado exacto,
- último comando largo,
- PID/log/checkpoint si aplica,
- siguiente acción concreta,
- riesgos abiertos,
- artefactos buenos actuales.

REGLAS DE SEGURIDAD:
- No borres checkpoints, adapters, merged models ni datasets útiles sin archivarlos antes.
- Ojo: `train_fg.py` puede limpiar `out_fg/lora`, `out_fg/merged-bf16` y `out_fg/ckpt` al arrancar. Antes de relanzar después de un crash, implementa o usa una forma segura de resume/no-clean, o archiva primero.
- No hagas cambios destructivos fuera del proyecto.
- No instales dependencias salvo necesidad real y documentada.
- No ejecutes tools reales peligrosas en tests nocturnos; usa mocks cuando abran apps, compren, publiquen o modifiquen estado externo.

BUCLE DE TRABAJO:
Repite hasta la fecha límite:
1. Medir estado actual.
2. Validar dataset, masking, schemas, args, duplicados, fuga train/holdout y cobertura.
3. Entrenar o reanudar entrenamiento.
4. Monitorear logs, GPU, loss, checkpoints y errores.
5. Evaluar checkpoint/final contra holdout, router, multilingual, `no_tool`, args, chains y casos adversariales.
6. Comparar contra baseline y contra el mejor checkpoint anterior.
7. Si hay fallas, corregir con datos focalizados o ajustes mínimos de training.
8. Rebuild, dryrun, reentrenar o continuar desde checkpoint.
9. Guardar resultados, métricas y decisión en `ops/NIGHT_RUN_STATE.md`.

OBJETIVO TÉCNICO:
Maximizar calidad real de tool-calling para Baxy:
- 0 tools inventadas.
- 0 args fuera de schema.
- 0 JSON/calls mal formadas.
- Alta precisión en selección de tool.
- Buen comportamiento con tools parecidas.
- Buen `no_tool` para pedidos conversacionales, ambiguos o no accionables.
- Buen multilingüe: es/en/pt/fr/de/it.
- Buen encadenado multi-step cuando el runtime devuelva resultados de tool.
- Baja latencia y artifact final usable en runtime.

COMANDOS BASE:
Usa PowerShell en Windows.

Validación inicial:
```powershell
cd "C:\Users\usuario\Desktop\ETC\Programacion\FunctionGemma\finetune_llm"
$PY="C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\.venv_ft\Scripts\python.exe"
& $PY build_fg_trainset.py
& $PY train_fg.py --dryrun
```

Detectar entrenamiento vivo:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*train_fg.py*' } |
  Select-Object ProcessId, CommandLine
nvidia-smi
```

Entrenamiento si no hay uno vivo y todo está verde:
```powershell
$PY="C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\.venv_ft\Scripts\python.exe"
& $PY -u train_fg.py --epochs 1 > train_run.log 2>&1
```

Durante training:
- Monitorea `train_run.log`.
- Espera checkpoints en `out_fg/ckpt/checkpoint-*`.
- Si hay OOM, baja batch/accum/max_seq con criterio y documenta.
- Si el entrenamiento termina, verifica que existan `out_fg/lora` y `out_fg/merged-bf16`.

Post-train:
1. Evalúa con scripts existentes en `scripts/`.
2. Corre comparativas contra baseline si existen.
3. Prueba casos manuales difíciles.
4. Cuantiza solo cuando el modelo merged sea bueno:
```powershell
& $PY quantize_fg.py
```
5. Valida GGUF en runtime/router si las herramientas locales están listas.

CRITERIO PARA SEGUIR ITERANDO (EVIDENCIA, NUNCA ESPECULACIÓN):
PROHIBIDO extender tiempo o reentrenar con justificaciones vagas tipo "quizás/puede ser/hay
probabilidad de que ayude". Cada iteración o pedido de más tiempo DEBE apoyarse en:
(a) una FALLA CONCRETA medida en el eval (ej. "confunde tool X con Y en N casos del holdout"), Y
(b) una HIPÓTESIS de fix CON FUNDAMENTO (paper/doc/experiencia real que mida que ese cambio corrige eso),
y se trata como challenger MEDIDO vs champion. Si no hay una mejora medible esperable con evidencia,
SE PARA y se declara el TECHO. "Entrenar otra vez por las dudas" NO es aceptable.

No entrenes epochs extra a ciegas. Entrena más solo si:
- eval mejora,
- fallas identificadas se corrigen con datos,
- loss/checkpoint no muestran degradación,
- no_tool no empeora,
- args/schema siguen perfectos.

Si una métrica empeora, conserva el mejor artefacto anterior como campeón y trata el nuevo como challenger.

SALIDA FINAL ESPERADA:
Al terminar o al llegar a la fecha límite, deja:
- mejor checkpoint/modelo elegido,
- merged bf16,
- GGUF Q8_0 si pasó validación,
- reporte en `ops/NIGHT_RUN_STATE.md`,
- comandos exactos para usarlo en Baxy,
- lista corta de fallas residuales si queda alguna.

NO TE DETENGAS POR CANSANCIO, INCERTIDUMBRE MENOR O UNA FALLA NORMAL.
Diagnostica, corrige, reintenta y deja estado recuperable. Solo pide ayuda si hay una decisión irreversible, credenciales faltantes o riesgo real de dañar archivos importantes.
```