# TOOLS-REDUCE — ESTADO (FunctionGemma para la rama Baxy `Tools-Reduce`)

**Misión nueva (2026-06-24):** reentrenar FunctionGemma-270M para el catálogo REDUCIDO de Baxy
(rama `Tools-Reduce`): 110 funciones individuales (28 familias + `session` meta) en vez de las 525.
FG debe: elegir bien entre las 110, ABSTENERSE (`no_tool`) en capacidades ELIMINADAS
(terminal/paquetes/email/env/dev-meta) y chitchat, multilingüe es/en/fr/de/it/pt, args limpios.

**Champion previo INTACTO** (catálogo viejo 525): `../model/functiongemma-ft-270m-it-Q8_0.gguf`
(run9, md5 b4ac42db) + `archive/run9_ep5_merged`. NO se toca hasta validar el reducido.

## ====== 🏆 VEREDICTO 2026-06-25 ~07:00 — ITER3 = NUEVO CHAMPION DESPLEGADO ======
**CHAMPION = iter3** (full-FT 5ep, lr5e-5/constant, **bs2/accum8**, dataset 7892 con HARD-NEGATIVES de
abstención: distractores REALES medidos del encoder + categoría knowledge). GGUF md5 **8fa2b441**,
desplegado en `model/functiongemma-tools-reduce-270m-it-Q8_0.gguf` y slot Baxy. Merged en
`archive/run_reduce3_5ep_merged`. Backups: iter2 `-iter2-Q8_0.gguf`, iter3 `-iter3-Q8_0.gguf`.

### iter3 DOMINA a iter2 (held-out NUEVO `eval_fg_abstain_e2e.py`, FG aislado, subset encoder real):
| métrica | iter2 | **iter3** |
|---|---|---|
| **abstención-E2E total** | 76.3% | **89.5%** |
| **KNOWLEDGE** (preg conocimiento→no_tool) | 25% | **100%** |
| ABSTAIN-removed (terminal/pip/email/env/devmeta) | 81.2% | **87.5%** |
| CHITCHAT | 100% | 100% |
| CONTRAST-acción (anti over-refusal) | 90% | 90% |
| **acción producción-fiel** (eval_fg_reduced_e2e) | 95% | **97.5%** |
- **Qué subió la abstención (TAREA 3 RESUELTA en gran parte):** el champion iter2 abstenía 100% en eval
  AISLADO pero 76% en held-out real porque sus distractores de abstención eran tools NEUTRAS; nunca vio la
  tool tentadora REAL (computer_use/filesystem/web_search) junto a no_tool. FIX (When2Call 2504.18851 +
  SimpleToolHalluBench 2510.22977): hard-negatives con los distractores REALES medidos por
  `discover_tempting_subsets.py` (ops/tempting_subsets.json) + nueva categoría knowledge→no_tool.
- **Residual (email-FORWARD fr/de/pt + terminal-comando fr): iter4 lo intentó y FALLÓ el gate (RECHAZADO).**
  iter4 (md5 880e72e1, entrenado completo) subió ABSTAIN-removed 87.5→90.6 PERO REGRESÓ knowledge (100→50%),
  acción producción-fiel (97.5→87.5%, app_open→browser_open ×5) y contrast (90→80%). Trade neto negativo →
  **iter3 RESTAURADO como champion** (ambos slots = 8fa2b441). iter4 conservado como `-iter4-Q8_0.gguf`.
  Lección: el batch amplio de negativos (forward-email + "abrí terminal"/"ejecutá comando X") sobre-tunea la
  abstención y confunde el verbo abrir (app_open↔browser). Próximo intento: negativo MÍNIMO solo-forward-email.
- **LECCIÓN de recursos:** full-FT bs4/accum4 NO cabe en 31.8GB RAM (crashes MemoryError); usar bs2/accum8.
  Con máquina libre (cerrar navegadores/Discord/Steam) bs2 entrena sin problema; el cuello era contención de Baxy.

## ====== 🏆 VEREDICTO FINAL 2026-06-24 ~20:00 — ITER2 (champion previo, ahora backup) ======
**CHAMPION Tools-Reduce = iter2** (full-FT 5ep, lr5e-5/constant, dataset contrastivo 7763, loss 0.0148).
Desplegado: `model/functiongemma-tools-reduce-270m-it-Q8_0.gguf` (md5 4c8e5a87) + copiado a Baxy
`models/FunctionGemma/`. fg_router._FG_GGUF apunta ahí. Backups: iter1 en `model/functiongemma-tools-reduce-iter1-Q8_0.gguf`
+ `model/functiongemma-tools-reduce-iter2-Q8_0.gguf`. Merged: `archive/run_reduce2_5ep_merged`.

### MÉTRICAS (iter2 vs iter1):
| eval | iter1 | iter2 |
|---|---|---|
| **producción-fiel e2e** (eval_fg_reduced_e2e, subset encoder real) | 75% (30/40) | **95% (38/40)** |
| **cascade completo** (fg_emit 19 casos manuales) | 73→84% (con guard) | **94% (18/19)** |
| holdout (family-distractor, menos representativo) | 91.0% | 88.9% |
- iter2 ARREGLÓ de raíz: time→alarm/timer (multiling 64→93%), computer_use over-selection (abre notepad→app_open,
  whatsapp→send_message), steam↔app, battery↔device_settings. Vía datos CONTRASTIVOS con distractores REALES del
  encoder forzados (`gen_reduced_contrastive.py`). El único miss del cascade ("cuánta RAM"→no_tool) es el act-peak
  gate (top1 0.398<0.40, decisión del usuario), NO FG → FG-attributable 18/18.
- Trade medido: -2pp holdout (eval optimista con distractores de familia) por +20pp en producción (el que importa).
- Residual (long-tail 270M): browser↔browser_real, app_open↔app_search (hermanas near-idénticas). Mitigado por router.
- Router guard fix (bare-read tools) SIGUE aplicado (complementa; "qué hora es" robusto a 2 niveles).
- **Validación final**: 32 tests invariantes PASS, encoder gates sin regresión (0.985/0.930/0.979), deployed-slot boot OK.
- **LECCIÓN**: el eval con distractores de familia (build_tools) es OPTIMISTA y NO predice producción. SIEMPRE validar
  con `eval_fg_reduced_e2e.py` (subset del encoder real). El holdout 91% de iter1 escondía un 75% real.

## (histórico) ITER2 RETRAIN: task `b0pcxumwi`, log `train_reduce2.log`.
Full-FT 5ep, lr5e-5/constant, **bs4/accum4** (el usuario autorizó matar el server E2B :8080 que contendía la GPU →
sin contención, ~2.4s/it, ETA ~1.6h). Dataset contrastivo `curated/fg_train.jsonl` (7763, validado, 0 dead).
NOTA: si el E2B vuelve a contender y crawlea (s/it>6, util<30%, VRAM~16GB), usar bs2/accum8 (mismo eff batch 16).
AL TERMINAR: archivar→quantize `--out functiongemma-tools-reduce-270m-it` → **eval producción-fiel**
`Probando Gemma 4/eval_fg_reduced_e2e.py` (target >75%, time/battery/steam OK) + holdout. Promover (pisar GGUF iter1)
SOLO si supera. El router-guard fix ya está aplicado (independiente del GGUF; suma).

## ✅ FIX DEL ROUTER (2026-06-24 ~16:30, SIN GPU — el usuario propuso optimizar el router):
Se editó SOLO `Probando Gemma 4/gemma4_agent/routing/fg_router.py` (capa FG, NO el encoder/KVA):
- **`_BARE_READ_TOOLS`** {time,battery,disk,public_ip,get_system_resources}: el guard read-vs-write ya
  existía pero no reconocía estas lecturas de nombre-desnudo → "¿qué hora es?" (si FG elegía alarm_create,
  MUTANTE) caía en no_tool/alarma. Ahora el guard cae en `time`. RESULTADO (fg_emit, CPU): "qué hora es"→
  system{time} en 5/6 idiomas (antes alarm_create/timer_list). **Bug DAÑINO (setear alarma sin querer) ELIMINADO.**
- Cascade e2e (19 casos manuales, fg_emit): **73% → 84%** (o ~95% si computer_use cuenta como OK).
- **DECISIÓN del usuario**: computer_use NO es un fallo (logra la meta, solo es más pesado/lento que la tool
  directa) → se DEPRIORIZA (no se fuerza la tool específica). Residual real = act-peak floor en "cuánta RAM
  tengo" (top1 0.398 < 0.40, decisión de gate del usuario, NO tocado) + german-timer/battery↔device_settings
  (selección de FG → lo arregla el retrain iter2).
- Eval producción-fiel: `Probando Gemma 4/eval_fg_reduced_e2e.py` (subset del encoder real, NO build_tools).
  OJO: ese eval usa F._ask (FG crudo, SIN guards) para aislar FG; para ver el efecto de los guards usar fg_emit.

## 🔁 (histórico) ITER2 dataset — RETRAIN con CONTRASTIVOS — task `bby3m18o1` (detenido), log `train_reduce2.log`
**Por qué reentrenar (FALLA MEDIDA + fix fundamentado):** el eval offline (build_tools, distractores de
FAMILIA) daba 91% holdout / 78-78 gate, PERO el eval PRODUCCION-FIEL (`Probando Gemma 4/eval_fg_reduced_e2e.py`,
subset del ENCODER real R.subset = cross-family + computer_use) dio **75% (30/40)**. Los 10 fallos = 100% de FG
(0 encoder-miss): time→alarm_create (×5 idiomas), →computer_use (notepad/whatsapp/discord ×3), steam_open→app_open,
battery→device_settings. Causa: el encoder mezcla system+notification (time vs timer/alarm) e inyecta computer_use;
el training nunca puso esos confusables en el mismo subset. FIX: `gen_reduced_contrastive.py` →
`curated/hc/batch_reduced_contrastive.jsonl` (287 ej) con los distractores REALES de produccion FORZADOS (`distract`):
time↔timer/alarm simetrico, app_open/send_message/steam_open/web_search/describe_screen vs computer_use,
battery/ram/disk vs device_settings. Dataset iter2: train=7763 (todo PASS). Comando = mismo de iter1.
- **LECCION CLAVE:** el eval con distractores de FAMILIA es OPTIMISTA; SIEMPRE validar con `eval_fg_reduced_e2e.py`
  (subset del encoder real) — es el unico que predice produccion. iter1 GGUF DEPLOYADO sigue (challenger iter2 lo bate o no).
- AL TERMINAR iter2: archivar→quantize `--out functiongemma-tools-reduce-270m-it` (re-quantiza, pisa el GGUF iter1
  SOLO si mejora) → `eval_fg_reduced_e2e.py` (target >75%, esp. time/computer_use OK) + holdout. Promover si supera.

## ✅ ITER1 (2026-06-24 ~13:20): TRAINING reducido — task `b931v9vnz`, log `train_reduced.log` (COMPLETO, deployado)
Comando EXACTO (relanzar igual si muere; out_fg se limpia al arrancar salvo --no-clean):
```
cd "C:\Users\usuario\Desktop\ETC\Programacion\FunctionGemma\finetune_llm"
$PY="C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\.venv_ft\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"; $env:SLIM_SCHEMAS="1"
& $PY -u train_fg.py --full --lr 5e-5 --scheduler constant --epochs 5 --bs 4 --accum 4 > train_reduced.log 2>&1
```
- full-FT, lr5e-5/constant (receta Google = champion). bs4/accum4 (eff 16, estable con el E2B server :8080 ocupando ~4.2GB).
- Dataset: `curated/fg_train.jsonl` (7587) + `fg_holdout.jsonl` (477). 2370 pasos (~474/epoch). ETA ~2-2.5h.
- Si crashea a mitad: hay checkpoints en `out_fg/ckpt/checkpoint-*` → relanzar con `--no-clean --resume <ckpt>`.
- Salida final: `out_fg/merged-bf16` (epoch 5). Si OOM: bajar a `--bs 2 --accum 8`.

## SIGUIENTE (al terminar el training)
1. **Archivar** merged → `archive/run_reduce_5ep_merged` (cp de out_fg/merged-bf16).
2. **Cuantizar** a GGUF con NOMBRE NUEVO (NO pisar champion):
   `python quantize_fg.py --out functiongemma-tools-reduce` → `../model/functiongemma-tools-reduce-270m-it-Q8_0.gguf`
   (verificar el flag real de quantize_fg.py; si no acepta --out, cuantiza al default y `cp` al nombre nuevo).
3. **Evaluar** (holdout reducido + abstención + multilingüe + casos manuales). Eval local:
   `python eval_night.py --model out_fg/merged-bf16 --greedy --n 477` (OJO: eval_night usa
   `../tool_schemas_decomposed.json` para args — superset, ok para nombre de tool; el holdout es el reducido).
   Probes: abstención removed-capability (ejecuta pytest/instala requests/envia correo→no_tool) +
   contrastivo (instala doom en steam→steam_open). Multilingüe: las 6 lenguas, misma función por intención.
4. **GATES de promoción** (vs comportamiento esperado, no vs champion-525 que es otro catálogo):
   - tool-acc holdout alto (esperado > champion por menos hermanas confusas: ~80% de los clusters densos
     de run9 —browser_real/database/docker/csv/firewall— DESAPARECEN en el reducido).
   - no_tool: abstención removed-capability OK + chitchat OK, SIN over-abstención en acciones reales.
   - 0 inventadas, 0 args fuera schema, calls bien formadas.
   - multilingüe sin degradar de/pt.
5. **Si pasa**: deploy en Baxy (ver abajo). Si NO: iterar (datos/epochs), champion-525 NO sirve para el
   catálogo reducido de todas formas (emite tools que ya no existen → debe retrainerse sí o sí).

## DEPLOY en Baxy (solo si gates pasan)
1. `cp ../model/functiongemma-tools-reduce-270m-it-Q8_0.gguf` a `Probando Gemma 4/models/FunctionGemma/` (si no está ahí).
2. Editar `Probando Gemma 4/gemma4_agent/routing/fg_router.py`:
   - `_FG_GGUF` → apuntar al nuevo `functiongemma-tools-reduce-270m-it-Q8_0.gguf`.
   - **FIX no_tool injection** (HACER): el slim reducido de Baxy NO tiene `no_tool` y el filtro
     USED_TRUE_TOOL_NAMES lo dropearía → `subset()` actualmente NUNCA inyecta no_tool al subset de FG.
     Cambiar `subset()` para inyectar un `_NO_TOOL_SCHEMA` inline SIEMPRE (restaura el contrato con el
     que FG fue entrenado). El builder/training YA tiene no_tool (en reduced_catalog/slim local).
3. Validación Baxy (desde el repo Baxy):
   ```
   pytest -q gemma4_agent/tests/test_router_coverage_invariant.py `
     gemma4_agent/tests/test_tool_registry_contract.py::TestSchemasAPI `
     gemma4_agent/tests/test_tool_registry_contract.py::TestImplsIntegrity
   python scripts/router_eval.py --split both --slices       # mide el ENCODER (NO debe regresar: dev0.985/hold0.930)
   python scripts/eval_multilingual_probe.py                 # ENCODER (0.979, no regresa por cambiar FG)
   ```
   NOTA: router_eval + multilingual_probe miden el ENCODER/planner (select_tool_names), NO FG → planos
   ante el cambio de GGUF. El gate REAL de FG es end-to-end (fg_emit): casos de acción + abstención manuales.

## DECISIONES CLAVE (fundamentadas) — qué se hizo y por qué
- **Catálogo reducido = subconjunto ESTRICTO del viejo** (110 ⊂ 525, 0 nombres nuevos) → cirugía del
  dataset es PURO subtractivo. Builder apunta a `reduced_catalog/` vía `FG_CATALOG_DIR` (no pisa el slim viejo;
  reproduce champion sin cambios si no se setea). `row()` DROPEA targets muertos, `build_tools()` arma
  distractores solo del set reducido → automático.
- **`no_tool`**: ausente del slim reducido (build_strict_slim no lo incluye). Agregado a `reduced_catalog/`
  slim LOCAL (training). En Baxy se inyecta inline en el router (no se toca el slim 110 de Baxy).
- **Abstención removed-capability** (`gen_reduced_abstain.py` → `curated/hc/batch_reduced_abstain.jsonl`):
  terminal/pip/npm/exe/email/env/dev-meta → no_tool, MULTILINGÜE, con distractores tentadores FORZADOS
  (`force` en build_tools: "instala X con pip"→no_tool CON app_open/steam_open en el subset = distrib. real
  del router). Alineado con `fix_eval_corpus_for_reduced_catalog.py` (clase A2/B). CONTRASTIVO: "instala
  JUEGO en steam"→steam_open (NO no_tool) para no sobre-generalizar. Evidencia: When2Call (2504.18851),
  SimpleToolHalluBench (2510.22977), AgentFlux (2510.00229: menos tools = menos carga cognitiva del SLM).
- **arg-less fix**: `play` agregado a VALUE_REQUIRED (era 17% positivo, "pon música"→play{} contaminaba);
  cadenas que contienen tool VALUE_REQUIRED se DESCARTAN (no guardan args → vacío contamina). Tras fix:
  todas las paramétricas 99-100% positivo.
- **NO se entrena "reinicia el PC"**: el slim reducido NO tiene restart/shutdown (cortados por strict-slim).
  Mapear a una función inexistente = enseñar a alucinar. Queda emergente/ausente (si se quiere, re-agregar
  system_restart al slim con evidencia, NO huérfano).
- **Multilingüe (no es-only)**: el experimento es-only (2026-06-19) FALSIFICÓ que especializar ayude
  (empate 89.7%); la selección de tool transfiere cross-lingual → se mantiene multilingüe.

## VALIDACIÓN DATASET (validate_dataset.py con FG_CATALOG_DIR) — TODO PASS
estructura ok, 0 no-parseables, 0 inventadas, 0 args fuera schema, 0 fuga, 0 dups, no_tool 10.7%,
paramétricas 99-100% positivo, cobertura 108/111 ≥40 (3 en 32-36: browser_search/public_ip/wifi_status), 111/111 ≥10.

## ARCHIVOS NUEVOS/EDITADOS (lado FunctionGemma)
- `reduced_catalog/` (slim+cats+amap synced de Baxy + no_tool en slim) + SOURCE.txt
- `build_fg_trainset.py` (FG_CATALOG_DIR override + force distractors + play VALUE_REQUIRED + chains skip)
- `gen_reduced_abstain.py` → `curated/hc/batch_reduced_abstain.jsonl` (230 ej: 160 abstain + 70 contrastivo)
- `validate_dataset.py` (FG_CATALOG_DIR-aware)
- Dataset: `curated/fg_train.jsonl` (7587) / `fg_holdout.jsonl` (477) = REDUCIDO multilingüe
- Backup es-only scratch: `archive/pre_tools_reduce_*/`
