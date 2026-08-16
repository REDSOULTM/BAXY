# RETRAIN COORDINADO DEL ROUTER DE BAXY — estado vivo

**Inicio:** 2026-06-18 ~23:00 (-04). **Deadline DURO:** 2026-06-19 10:00am.
**Paquete fuente:** `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\documentacion\_fg_training_package\` (README = fuente de verdad).
**Repo donde corre el encoder/eval (Baxy):** `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\` (módulo `gemma4_agent`).
**Repo KVA + FG:** `C:\...\FunctionGemma\` (build_kva_gate.py, fg_router_ft.py cargan `router/data/router_encoder_ft`).
**venv ENCODER/EVAL:** `Probando Gemma 4\.venv_router_train\Scripts\python.exe` (torch 2.6.0+cu124 CUDA✓, ST 3.3.1, sklearn 1.8.0).
  ⚠️ `.venv_ft` (torch 2.7.0) **SEGFAULTEA** al cargar SentenceTransformer "pelado" (cpp-ext rota) — router_eval crashea (exit 139). Usar SIEMPRE `.venv_router_train` para encoder/eval/KVA.

## POR QUÉ (acoplamiento medido)
Cascada de 3 modelos que comparten geometría de embeddings: Encoder MiniLM-FT → KVA gate (logística SOBRE
los embeddings) → FG_ACT_PEAK (umbral 0.52 sobre top-1 del encoder) → FunctionGemma 270M. Retrain del
encoder corre TODO el espacio de scores → KVA y act-peak quedan STALE y hay que recalibrarlos CON el
encoder nuevo en la MISMA corrida. Por eso no se despliega el encoder solo.

## ARQUITECTURA / RUTAS CLAVE (verificado en código)
- Encoder canónico runtime (Baxy): `gemma4_agent/data/router_encoder_ft`.
- Encoder copia (FunctionGemma, lo usan build_kva_gate.py y fg_router_ft.py): `FunctionGemma/router/data/router_encoder_ft`.
- Override de encoder para el router sin swap: env `GEMMA4_SEMANTIC_MODEL=<dir>` (semantic_router.py:348/377).
- Entrenamiento encoder: `scripts/train_router_encoder.py` (Baxy). Escribe a `GEMMA4_ENCODER_OUT_DIR` (default in-place).
  Receta commiteada: base=paraphrase-multilingual-MiniLM-L12-v2, epochs=3, batch=64, MultipleNegativesRankingLoss,
  seed=42, n_pairs=14544. Lee tool2vec_queries.jsonl + dev-split de router_eval_corpus.curated.jsonl + dev-split de
  router_corpus_curated_ft.jsonl. Holdout EXCLUIDO por hash estable (salt "router-eval-2026-05-20", q%5==0 → holdout).
- FG_ACT_PEAK: `gemma4_agent/routing/fg_router.py:64` = `float(os.environ.get("GEMMA4_FG_PEAK","0.52"))`.
- KVA: `FunctionGemma/build_kva_gate.py` → `kva_gate.json` (coef 384d + intercept + threshold 0.87). Usa el encoder
  vía `fg_router_ft.FTRouter().st` (carga `FunctionGemma/router/data/router_encoder_ft`).
- Gate de eval: `scripts/router_eval.py --split both --slices --equiv` (per-idioma + dev/holdout).

## DATOS (paquete == repo Baxy, ya sincronizado — counts verificados)
- tool2vec_queries.jsonl 8436 (incluye +149 now-playing/status NUEVAS; antes 8287).
- router_corpus_curated_ft.jsonl 6503; router_corpus_real_logs.jsonl 1071.
- eval/router_eval_corpus.curated.jsonl 2102 = **HELD-OUT, el GATE, NO entrenar sobre esto** (el script lo excluye por hash).
- new_data/nowplaying_status_corpus.jsonl 149; new_data/_fg_corrections_week.jsonl 142.

## GATE DE EVAL (de antemano, no negociable)
1. Recall global ≥ 0.95 en holdout (committeado 0.9521; NO empeorar; ≤ -0.005 de margen → investigar).
2. Ningún idioma/subgrupo regresa: recall por es/en/pt/it/fr/de no baja vs baseline.
3. El fix rutea: now-playing/status ("qué suena"/"what's playing"/"cuánta batería") → familia correcta top-1 Y
   por encima del FG_ACT_PEAK re-medido.
4. El ruido NO sube de más (~0.63 extra-tools/turno committeado; vigilar over-offering).
Si NO pasa → NO desplegar. Todo a dirs TEMP + swap atómico, reversible.

## PLAN / CRONOGRAMA (deadline 10:00)
- [P0 ~23:00-23:40] Entender + venv + BASELINE eval (encoder commiteado) → números "antes" (global+por idioma+now-playing). **EN CURSO**
- [P1] Backup encoder; retrain encoder → TEMP `router_encoder_ft_NEW` (GEMMA4_ENCODER_OUT_DIR). Receta commiteada primero.
- [P2] Eval encoder NUEVO via GEMMA4_SEMANTIC_MODEL → gate (global, por idioma, now-playing/status). Si falla → iterar (oversample clase rara now-playing, evidencia README "rare class SOTA").
- [P3] Re-medir FG_ACT_PEAK (chitchat vs acción multiling, esperado ~0.44). Actualizar GEMMA4_FG_PEAK/fg_router.py.
- [P4] Re-fit KVA: copiar encoder nuevo a FunctionGemma/router/data/router_encoder_ft (backup antes) → build_kva_gate.py → kva_gate.json nuevo. Smoke trampas→no_tool / canarios→FG.
- [P5] Swap atómico encoder Baxy; eval final --split both --slices; reporte antes/después por idioma. Artefactos listos para Baxy.
- [P6 si sobra] FunctionGemma retrain con 142 correcciones (lever más grande, 86/122 errores son de FG). El más largo (full-FT).

## DECISIONES (con evidencia)
- (P0) Reentreno con receta commiteada primero (epochs=3/batch=64/MNRL) porque es la que dio 0.9521; cambios = challenger medido vs baseline. README confirma receta.

## ⚠️ HALLAZGO CRÍTICO (el README subestimó el acoplamiento)
El retrain del encoder NO acopla solo KVA+act-peak. `scripts/router_ft_pipeline.py` (proceso canónico
commiteado) reconstruye CON el encoder nuevo, en orden:
  1. `tool2vec_centroids.npz` (router_tool2vec_build.py) — centroides de queries sintéticas. El tool-vector
     runtime = blend(0.6*centroid + 0.4*desc) (GEMMA4_TOOL2VEC_ALPHA=0.6). Centroides viejos = espacio viejo → STALE.
  2. `router_exemplars.npz` (router_exemplar_build.py) — store de exemplars (query→tool) embebido; el exemplar_router
     compara query-time vs estos vectores PRE-computados; mezclar 2 espacios corrompe el margen de abstención (bug medido 2026-05-30).
  3. `abstain_head.json` (train_abstain_head.py --recall-floor 0.95; luego threshold=0.68) — head sobre features de embeddings.
  4. luego eval. Todos respetan `GEMMA4_SEMANTIC_MODEL` → driveable apuntando al dir RETRAIN.
SIN reconstruir 1-3, el eval del encoder nuevo mezcla espacios y es BASURA. Backups en `gemma4_agent/data/_artbak_bak_pre_retrain_2026-06-18/`.

### GAP DEL PIPELINE CANÓNICO: `tool_head.json` también es encoder-space y NO lo reconstruye
`tool_head.json` = "anti-bloat head" (per-tool logistic sobre el embedding 384d del encoder, ON por default
GEMMA4_TOOL_HEAD!=0) — ES quien arma el subset por umbral por-tool. Trainer: `scripts/train_tool_head.py`
(dev rows + tool2vec, holdout excluido por hash, embeba vía semantic_router). El pipeline canónico lo OMITE → gap.
DECISIÓN: lo reconstruyo también con el encoder RETRAIN (mismo proceso, holdout-excluido) para que TODA la pila
quede en una sola geometría. Sin esto, el subset opera en geometría stale → ruido/recall corrompidos.
Artefactos encoder-space a reconstruir = {tool2vec_centroids, router_exemplars, abstain_head, tool_head} + KVA (FunctionGemma).

## ⚠️ FUGA PRE-EXISTENTE (consistente baseline-vs-nuevo)
`router_exemplar_build.py` embebe TODO el eval corpus (incluido holdout) como exemplars → el holdout recall de
router_eval está MEMORIZADO (por eso da 1.0, no 0.95). Así se construyó el commiteado también → comparar baseline vs
nuevo con el mismo proceso es justo, pero el recall NO discrimina. Señal LIMPIA del encoder = probe now-playing/status
(suggest_tools_scored directo; las 149 NO son exemplars, vienen de new_data) + no-tool keep + ruido + probe frases frescas.

## ⚠️ notes_status NO fixeable en lean (config, no encoder)
8 filas notes_status → exp=`notes_tasks`, que `GEMMA4_LEAN_TOOLS=1` (producción) ELIMINA del catálogo → nunca top1.
Residual de config, no falla de encoder. NO bloquea el gate. (now_playing→media, sysinfo→system,
display_status→device_settings, browser_nav→browser, app→app SÍ están en lean y son fixeables.)

## BASELINE MEDIDO (encoder commiteado, 2026-06-18 23:30) — números "ANTES"
- **router_eval (con --equiv)**: dev recall 1280/1280=1.000, no-tool keep 0.9975; holdout recall 334/334=1.000,
  no-tool keep 0.9891. RUIDO ~0.62-0.66 extra/turno. → recall ya saturado en este corpus (subset generoso);
  el holdout es ~99% español (per-idioma del holdout casi sin señal non-es). El recall NO es la métrica que discrimina.
- **FIX now-playing/status (probe sobre las 149, expected==top1)**: **71.8%** (107/149).
  Por idioma: es 25/42(59%!), en 20/28, de 14/18, fr 15/21, it 16/20, pt 17/20.
  Por cat: now_playing 42/53, sysinfo 32/42, display_status 11/17, notes_status **0/8**, browser_nav **2/7**.
- **ACT-PEAK basis**: chitchat top1 p50=0.447/p90=0.608/max=0.816; acción top1 p50=0.487/min=0.264. **SOLAPAN fuerte**,
  no hay umbral limpio (a 0.52 pasa solo 35.6% acción; equilibrio ~0.47 con 61%/58%). Esto motiva el retrain
  (subir acción y comprimir chitchat para que ~0.44 separe — README espera ~0.44).
- NOTA HONESTIDAD: las 149 del probe están 100% en tool2vec (training) → post-train mide fit, no generalización.
  Mitigación: escribir probe de frases FRESCAS (no en corpus) para señal de generalización + el eval corpus es el gate held-out.

## RESULTADO ENCODER NUEVO (RETRAIN + pila reconstruida, 2026-06-18 23:40)
- **FIX now-playing/status top-1: 71.8% → 87.2%** (130/149). TODOS los idiomas suben (es 59%→88%, en 71%→82%,
  de 78%→89%, fr 71%→90%, it 80%→85%, pt 85%→90%). now_playing 51/53, sysinfo 36/42, display_status 16/17,
  browser 6/7, app 21/22. notes_status 0/8 (config lean, no encoder).
- **Generalización (frases FRESCAS no-en-training, n=28): 78.6%** (sysinfo 8/8, app 4/4, browser 3/4, display 3/4,
  now_playing 4/8). Generaliza de verdad.
- **act-peak**: score acción p50 0.487→0.581; a thr=0.44 pasa 87.2% acción / corta 44.1% chitchat (antes 35.6%/47%).
  Chitchat NO bajó a 0.41 como esperaba el README (sigue p50~0.459) pero la acción subió lo suficiente.
- **router_eval holdout (equiv)**: 0.9521 (= committeado EXACTO), no-tool keep 1.000 (era 0.989), RUIDO 0.58 (era 0.66).
  dev (equiv) 0.9430, no-tool keep 1.000. → midiendo 2×2 estricto/equiv vs baseline real para confirmar si hay regresión de recall.

## 🐞 CAUSA RAÍZ DE LA "REGRESIÓN" DE RECALL (mi error de rebuild, NO el encoder) — 2026-06-18 23:50
Baseline REAL desplegado (old enc + old art) = holdout recall **1.0000** (estricto Y equiv), NO 0.9521.
Mi rebuild lean dio 0.9521 (16 misses). Los 16 misses son TODOS tools LEAN-CUT: audio_device×4, reminder×4,
input×3, clipboard×3, routine, office. Subset cae a ['safety','session'].
EVIDENCIA: deployed exemplars retienen labels de cut-tools (audio_device=9, reminder=43, clipboard=16, input=59);
mis exemplars lean = 0 de cada uno. `router_exemplar_build.py:56` filtra `if tool in known` → en lean, los cut-tools
salen de `known` → labels a vacío → exemplar no rutea. Deployed tool_head = 61 tools (FULL); mi lean = 27.
**RECETA DESPLEGADA = construir artefactos en modo FULL (GEMMA4_LEAN_TOOLS=0), SERVIR en lean.** Mi error: construí en lean.
FIX: reconstruir exemplars + tool_head + abstain en FULL. (Centroides ya cubren 62, independientes de lean.)
El FIX now-playing NO se ve afectado (usa suggest_tools_scored crudo, encoder-level).

## ✅ GATE FINAL PASA — DESPLEGABLE (2026-06-19 00:15)
Pila completa swapeada en Baxy (encoder + 4 artefactos FULL + act-peak 0.44 + KVA 0.89). Eval end-to-end SIN
env override (usa el encoder prod swapeado):
- **holdout recall 1.0000** (0 misses, = baseline desplegado), **dev 1.0000**, **no-tool keep 1.0000** (era 0.989).
- RUIDO dev 0.58 / holdout 0.64 (≤ baseline 0.62/0.66). TODOS los idiomas (es/en/fr/de/it/pt) recall 1.000.
- **FIX now-playing/status 87.2%** (era 71.8%), **frescas/generalización 78.6%**. (idénticos a la eval TEMP → swap consistente)
- KVA refit: thr 0.89, conocimiento→no_tool 74.3%, acción preservada 99.1%, 7/7 trampas + 6/6 canarios OK.
GATE: (1) recall≥0.95 sin regresión ✓1.0 (2) ningún idioma regresa ✓ (3) fix rutea ✓71.8→87.2 (4) ruido no sube ✓.

### ESTADO REQ: encoder swapeado a Baxy (router_encoder_ft) + FunctionGemma (router/data). Artefactos FULL en prod.
Residuales aceptables: notes_status 0/8 (lean corta notes_tasks); "is ComfyUI running"→terminal/dependency (ambiguo,
defendible); "what's on right now"→verify (frase ambigua). Core (qué suena, batería, RAM, monitores) rutea bien.

## BACKUPS / REVERSIBILIDAD (todo recuperable)
- Baxy encoder viejo: `gemma4_agent/data/router_encoder_ft.OLD_swapped_2026-06-18` (+ `.bak_pre_retrain_2026-06-18`).
- Baxy artefactos viejos: `gemma4_agent/data/_artbak_bak_pre_retrain_2026-06-18/` (centroids/exemplars/abstain/tool_head).
- Baxy KVA viejo: `gemma4_agent/data/fg/kva_gate.json.bak_pre_retrain_2026-06-18`.
- FunctionGemma encoder viejo: `router/data/router_encoder_ft.bak_pre_retrain_2026-06-18`; KVA: `kva_gate.json.bak_pre_retrain_2026-06-18`.
- ROLLBACK: restaurar esos archivos + `fg_router.py` FG_ACT_PEAK→0.52 (o `GEMMA4_FG_PEAK=0.52`).

## ONNX (HECHO): `router_encoder_ft/model_int8.onnx` (118MB) re-exportado, paridad validada (holdout 1.0, now-playing 88.6%).

## PASO 4 FG — MEDIDO, NO justificado (TECHO declarado) — 2026-06-19 ~01:15
Evidencia-primero (server vivo PID 19904, champion run9): `FunctionGemma/fg_corrections_eval.py` corrió las 142 sobre el
sistema YA desplegado (encoder nuevo+KVA nuevo+FG champion): **family-HIT 52.1%, no_tool 13.4% (muchas correctas), WRONG 34.5%**.
Los 49 wrong = mayormente mismatch de categoría (tool correcto, ej app_opened="verify"), tools inexistentes (no hay lock/volume-down),
ambigüedad defendible (csv→data_analysis), gui↔uia. **Un full-FT arriesga el champion 88.3% con ganancia esperada baja → NO se reentrena.**
KVA universalidad: acciones multiling cortadas 2/30 nuevo = 2/30 viejo (sin regresión). Champion run9 intacto.
Mejoras futuras de bajo riesgo: tool_categories.json (app_opened→app), evaluar tool `lock`, +acciones de/fr/it/pt en build_kva_gate.

## ✅ CIERRE: la cascada (encoder+centroids+exemplars+tool_head+abstain+KVA+act-peak+ONNX) está DESPLEGADA, validada
(gate PASA, 0 regresión, fix 71.8→87.2/88.6%), documentada y reversible. FG: techo medido. Dir TEMP `router_encoder_ft_RETRAIN`
se conserva como backup extra. Reporte para Baxy: `Probando Gemma 4/documentacion/_ROUTER_RETRAIN_REPORT_2026-06-18.md`.

## RIESGOS ABIERTOS
- Dos copias del encoder (Baxy + FunctionGemma) deben quedar idénticas tras el swap, o KVA/runtime divergen.
- KVA refit usa fg_train.iter3.jsonl (FunctionGemma/finetune_llm/curated) para acción/conocimiento — verificar que existe.
