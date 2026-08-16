# Reporte — Retrain COORDINADO del router de Baxy (encoder + KVA + act-peak)
**Fecha:** 2026-06-19 (corrida nocturna). **Estado: ✅ DESPLEGADO y validado (gate PASA). Reversible.**

## TL;DR
Se reentrenó el encoder MiniLM con el corpus combinado (+149 now-playing/status) y se recalibró TODA la
pila acoplada con ese encoder. El fix de routing del clúster nuevo subió **71.8% → 87.2%** (top-1, multilingüe)
SIN regresión: recall holdout **1.0000** (= baseline), no-tool keep **1.0000**, ruido ≤ baseline, todos los
idiomas 1.000. Generalización a frases nuevas (no en training): 78.6%.

## QUÉ SE CAMBIÓ (artefactos en `gemma4_agent/data/`)
| artefacto | antes → después | cómo |
|---|---|---|
| `router_encoder_ft/` | encoder viejo → **reentrenado** | `scripts/train_router_encoder.py --epochs 3 --batch 64` (receta commiteada, holdout excluido por hash) |
| `tool2vec_centroids.npz` | → re-embebido | `scripts/router_tool2vec_build.py` con el encoder nuevo |
| `router_exemplars.npz` | → re-embebido | `scripts/router_exemplar_build.py` (modo FULL) |
| `tool_head.json` | → reentrenado | `scripts/train_tool_head.py` (62/62 tools, modo FULL) |
| `abstain_head.json` | → reentrenado (thr 0.68) | `scripts/train_abstain_head.py --recall-floor 0.95` |
| `fg/kva_gate.json` | thr 0.87 → **0.89** | `FunctionGemma/build_kva_gate.py` (re-fit logística sobre encoder nuevo) |
| `routing/fg_router.py::FG_ACT_PEAK` | 0.52 → **0.44** | re-medido (la acción del clúster nuevo sube; ver abajo) |

⚠️ **RECETA CLAVE (no obvia): los artefactos se CONSTRUYEN en modo FULL (`GEMMA4_LEAN_TOOLS=0`) y se SIRVE en
lean (`=1`).** Construir en lean filtra los labels de tools cortadas del exemplar store → regresión de recall
(audio_device/reminder/clipboard/input/office/routine ruteaban a `safety/session`). Confirmado: el deployed
tenía exemplars FULL. `tool2vec_centroids` es independiente de lean (cubre los 62 tools).

## NÚMEROS (gate held-out `router_eval_corpus.curated.jsonl`, 2102 filas, dev/holdout por hash estable)
| métrica | baseline (deployed) | nuevo | veredicto |
|---|---|---|---|
| holdout recall (equiv) | 1.0000 | **1.0000** | sin regresión ✓ |
| dev recall (equiv) | 1.0000 | **1.0000** | sin regresión ✓ |
| no-tool keep (holdout) | 0.989 | **1.000** | mejora ✓ |
| ruido medio (holdout) | 0.66 | **0.64** | mejora ✓ |
| recall por idioma (es/en/fr/de/it/pt) | 1.000 c/u | **1.000 c/u** | ningún idioma regresa ✓ |
| **now-playing/status top-1 (149, multiling)** | **71.8%** | **87.2%** | **el fix ✓** |
| — por idioma | es59/en71/de78/fr71/it80/pt85 | **es88/en82/de89/fr90/it85/pt90** | sube en TODOS ✓ |
| generalización frases FRESCAS (28, no-en-train) | — | **78.6%** | generaliza, no memoriza |
| KVA: acción preservada / trampas→no_tool | 99.1% / 7-7 | **99.1% / 7-7** | estable ✓ |

## FG_ACT_PEAK 0.52 → 0.44 (por qué)
El retrain corrió el espacio de scores: el top-1 de las acciones del clúster nuevo subió (p50 0.487→0.581).
A 0.44 pasa el **87%** de esas acciones (a 0.52 pasaba solo 36%), cortando el 44% del chitchat; el resto del
chitchat lo respaldan el gate KVA (conocimiento→no_tool 74%) + la abstención de FunctionGemma (~96%). Cascada
con deferral: ante la duda DEFIERE a FG. Override: `GEMMA4_FG_PEAK`.

## RESIDUALES CONOCIDOS (aceptables)
- `notes_status` 0/8: en lean, `notes_tasks` está cortado del catálogo → no puede ser top-1. Decisión de producto
  (re-incluir notes_tasks en lean si se quiere cubrir). NO es falla del encoder.
- "is ComfyUI running"/"está corriendo X" → terminal/dependency (en vez de system): ambiguo y defendible
  (chequear si un proceso corre ES terminal-ish).
- "what's on right now"/"was läuft gerade" → verify: frase muy ambigua. El core (qué suena, batería, RAM,
  monitores, acciones de/fr/it/pt) rutea bien.

## ONNX int8 (perfiles vram_lean usan `GEMMA4_ENCODER_ONNX=1`)
Re-exportado para el encoder nuevo: `gemma4_agent/data/router_encoder_ft/model_int8.onnx` (118 MB) vía
`scripts/export_encoder_onnx.py` (fix: `device="cpu"` para el venv GPU). Paridad validada por la ruta ONNX:
holdout recall 1.0000, todos los idiomas 1.000, now-playing **88.6%** (132/149; ~paridad con torch 87.2%, el int8
ayuda en un par de borderline). El runtime queda válido en AMBOS backends (torch y onnxruntime).

## ROLLBACK (todo respaldado, reversible)
- encoder: `router_encoder_ft.OLD_swapped_2026-06-18` (+ `.bak_pre_retrain_2026-06-18`)
- artefactos: `_artbak_bak_pre_retrain_2026-06-18/{tool2vec_centroids,router_exemplars,abstain_head,tool_head}`
- KVA: `fg/kva_gate.json.bak_pre_retrain_2026-06-18`
- act-peak: revertir `fg_router.py` a 0.52 (o `GEMMA4_FG_PEAK=0.52`)

## PASO 4 (FunctionGemma retrain) — MEDIDO y NO justificado (techo)
Antes de reentrenar FG (evidencia-primero, CLAUDE.md), se midieron las **142 correcciones de la semana sobre el
sistema YA desplegado** (encoder nuevo + KVA nuevo + FG champion run9, server vivo): `FunctionGemma/fg_corrections_eval.py`.
- **family-HIT 52.1%** (74/142) ya rutea bien | **no_tool 13.4%** (19; muchas correctas: preguntas factuales web/knowledge)
  | **WRONG-family 34.5%** (49).
- Análisis de los 49 "wrong": dominados por (a) **mismatch de categoría, NO error** — "is Spotify open?"→`app_opened`
  (categorizado "verify" pero es el tool correcto); (b) **tools inexistentes** en el schema slim — no hay `lock` ni
  `volume-down`, así que "Sperr den Computer"/"baisser le volume" no tienen destino válido (decisión de inventario, no training);
  (c) **ambigüedad defendible** — "analiza el csv y hazme gráfico"→`plot_line[data_analysis]` es razonable vs filesystem;
  (d) confusión hermana gui↔uia (clicks).
- Un full-FT de FG sobre estos labels (ambiguos/contradictorios) **arriesgaría el champion 88.3% con ganancia esperada baja**
  y NO crea los tools faltantes. → **TECHO declarado para FG este run.** Champion run9 se conserva.
- **Universalidad KVA verificada (no regresión):** acciones multilingües cortadas como conocimiento = **2/30 nuevo = 2/30 viejo**
  (en:1, de:1, idéntico). El retrain no perjudicó ningún idioma. (Mejora futura opcional: agregar acciones de/fr/it/pt al
  dataset de `build_kva_gate.py` para bajar ese 2/30; marginal.)
- **Mejoras de bajo riesgo recomendadas (no-training):** (1) mapear `app_opened`→familia app y status-checks a su familia en
  `tool_categories.json` (convierte ~5 "wrong" en hits); (2) evaluar agregar tool `lock` al schema slim si el producto lo quiere.

## REPRODUCIBILIDAD
venv: `.venv_router_train` (torch 2.6, ST 3.3.1) — `.venv_ft` (torch 2.7) SEGFAULTEA al cargar SentenceTransformer.
Orden: train_router_encoder → (FULL) router_tool2vec_build, router_exemplar_build, train_tool_head,
train_abstain_head(thr 0.68) → build_kva_gate → router_eval --split both --slices. Logs en `documentacion/_*.log`.
