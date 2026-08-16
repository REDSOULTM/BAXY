# VEREDICTO — Experimento FunctionGemma ESPAÑOL-ONLY (2026-06-19)

## DECISIÓN: ❌ NO PROMOVER. Se conserva el champion run9 (multilingüe). Experimento MEDIDO, hipótesis falsificada.

## Hipótesis (del dueño)
Un 270M es chico → especializarlo 100% en español daría más funcionalidad en español que diluirlo en 6 idiomas.
Plan: per-idioma, cada idioma su propio FunctionGemma.

## Qué se hizo (research-first + medido)
1. **Deep-research** del FT incremental (catastrophic forgetting, LoRA vs full, ratio datos) → validó full-FT + replay; ver `ops/RESEARCH_fg_incremental_ft_2026-06-19.json`.
2. **Dataset español-only**: filtro `FG_ES_ONLY=1` en build_fg_trainset (lang explícito en capa B/D, detector anti-no-es en A/C
   historial real). SLIM schemas (match champion). abstain-cap → ratio call:no_tool 12.8:1 (≈ champion 11.2:1).
   Resultado: 11642 ejemplos 100% español (99.93% limpio) en `curated/fg_train.iter_es.jsonl`.
3. **Training**: full-FT 5 epochs, lr5e-5/constant, bs4/accum4. Loss final 0.026. Merged en `archive/run_es_5ep_merged` (copiar de out_fg/merged-bf16).

## MEDICIÓN (comparación JUSTA — clave metodológica)
⚠️ El holdout es-only (728) NO sirve para comparar: el champion run9 VIO el 94% de esas filas en su training (iter3,
split aleatorio distinto) → su "93%" ahí es accuracy de ENTRENAMIENTO, inflado. El challenger es held-out limpio (81.7%).

**Comparación válida = frases españolas FRESCAS que NINGÚN modelo vio (39, gold inequívoco, mismo subset/distractores):**

| modelo | tool-acc frescas ES | parseables | inventadas | args malos | no_tool |
|---|---|---|---|---|---|
| **Challenger español-only** | **35/39 = 89.7%** | 100% | 2 | 3 | 51/51 |
| **Champion run9 (multilingüe)** | **35/39 = 89.7%** | 99.7% | 0 | 0 | 51/51 |

**EMPATE en español (89.7% ambos).** Fallos distintos, casi todos hermanas-near-sinónimas o golds discutibles
(challenger: alarm→timer, "mi IP"→public_ip[mejor que el gold], clipboard_read→write; champion: brightness→wifi_status[error claro],
web_search→web_open, whatsapp_send→send_message[válido]).

## CONCLUSIÓN (evidencia)
La especialización a español **NO dio ninguna mejora en español** (empate), mientras que el champion multilingüe
ADEMÁS cubre 5 idiomas más y tiene formato más limpio (0 inventadas/0 args-malos vs 2/3). → El champion es
estrictamente ≥ en todo eje. **El challenger NO supera el gate ("debe SUPERAR al champion") → se descarta.**

**POR QUÉ (fundamentado):** en tool-calling, la SELECCIÓN de tool es una habilidad **language-agnostic que transfiere
entre idiomas** (la geometría intención→tool es compartida). Los 28.5k multilingües enseñaron a elegir tool tan bien
para español como los 11.6k español-only — y los otros idiomas NO compiten por capacidad en esta tarea como sí lo
harían en GENERACIÓN de texto libre. Resultado: especializar pierde cobertura sin ganar nada. Coincide con el research
("más datos ayudan a la selección de tool, incluso cross-lingual").

## IMPLICANCIA PARA EL PLAN PER-IDIOMA
El plan de 6 modelos per-idioma **no rinde para esta tarea/tamaño**: cada modelo per-idioma sería ≤ el multilingüe
en su idioma (mismo techo) y perdería los demás. **Recomendación: un solo FunctionGemma multilingüe (run9) es óptimo.**
El esfuerzo rinde más en: (a) datos de los tools/patrones que fallan (el lever medido), (b) desambiguar hermanas-near-
sinónimas (el long-tail real, común a ambos modelos), (c) el router/cascada (ya hecho hoy).

## ESTADO / ARTEFACTOS
- **Champion run9 INTACTO**: `model/functiongemma-ft-270m-it-Q8_0.gguf` (md5 b4ac42db) — NO se tocó. Sigue desplegado.
- Modelo español-only (artefacto de referencia): `out_fg/merged-bf16` (sin cuantizar; NO desplegado).
- Dataset español-only: `curated/fg_train.iter_es.jsonl` / `fg_holdout.iter_es.jsonl`. Eval: `eval_{challenger,champion}_es.log`, `fresh_{challenger,champion}.log`.
- ⚠️ `curated/fg_train.jsonl` quedó = es-only (scratch). Para reconstruir el multilingüe del champion: `SLIM_SCHEMAS=1 python build_fg_trainset.py` (sin FG_ES_ONLY).
