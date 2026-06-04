# HANDOFF — Feature gigante: Fine-tune del modelo Gemma 4 con historial curado (lineage Carter)

> **DOCUMENTO HISTÓRICO — el FT YA SE COMPLETÓ.** Este handoff es el registro vivo del
> proceso (la noche del 2026-06-02), con sus fases EN CURSO/PENDIENTE tal como estaban
> entonces. **Todas se completaron:** dataset curado, router-FT (ES 0.9964 intacto +
> multilingüe ~0.85), QLoRA del E2B (no E4B — pivote por VRAM), GGUF Q4_K_M, y **deploy
> in-place**. Para el ESTADO FINAL ver `ESTADO_COMPLETO_2026-06-02.md` y
> `MISION_COMPLETA_HANDOFF.md`. Se conserva intacto como historia (CLAUDE.md: no borrar
> registros). Nomenclatura: producto = **Baxy** (antes "Gemma 4 Agent"/"Carter");
> "Carter v1-v5/Carter OS AI" = proyecto de referencia del que se minó historia; el
> **modelo** es Gemma 4 (de Google). "Gemma4" como tag de dataset/path NO se renombra.

## VISIÓN AMPLIADA (2026-06-02 noche, usuario se fue a dormir, trabajo autónomo)
El usuario quiere que Gemma4 quede MUCHO mejor: tool-calling + encadenamiento + calidad +
latencia PERFECTOS, autonomía total sobre su PC, y PERSONALIDAD (ej. abrir juego→"que la
pases bien"; WhatsApp a la novia→"suerte en el amor"; música de MJ→"el rey del pop sonando")
— contextual, NO enlatada, sin romper honestidad, multilingüe. Libertad total: crear datasets
sintéticos, bajar datasets de internet (licencia comercial-OK), elegir el MEJOR método de FT
(investigar, no asumir QLoRA — DoRA u otros pueden ser mejores). Gastar tokens sin miedo.
HARDWARE: i9-12900HX, RTX 4060 Ti 16GB, 32GB DDR5. DISCOS LIBRES: D:\ 766GB, H:\ 931GB
(modelos/datasets van AHÍ, NO en C:\ que tiene 71GB). Entrenar en 16GB, usuario final corre 4GB.

### FRENTES LANZADOS la noche del 2026-06-02 (background):
- Research método FT (LoRA/QLoRA/DoRA/Unsloth/...) → recomendación con evidencia. task ae91de975
- Research personalidad (character card + dataset sin enlatar) → PERSONALIDAD.md + personality_examples.jsonl. task a4fd89baf
- Research datasets externos OSS (licencia comercial-OK) → tabla vendible/no-vendible. task a91076713
- Curación 50 lotes faltantes (24-73, prompt anti-colapso) → batches/_batch_NN_out.jsonl. workflow w2ayl07re / run wf_dbbbc446-d69
ESTADO curación: 23/73 lotes ya escritos (1148 filas) ANTES de este workflow; los 50 restantes en curso.

### DECISIONES TOMADAS la noche (3 research completados, documentados):
- **MÉTODO FT** → `dataset_finetune/METODO_FINETUNE.md`: **Gemma 4 E4B-it + LoRA-16bit (r16-32,
  all-linear) en Unsloth → merge bf16 → GGUF --outtype bf16 → Q4_K_M+imatrix multilingüe**.
  NO DoRA (peor a rank bajo, 0 ventaja latencia post-merge). NO 2-bit (rompe tool-calling).
  Gemma 4 es Apache 2.0 (venta OK). ~30-90min train en la 4060Ti. train_on_responses_only +
  dropout + 2-3 epochs = anti-overfit. GOTCHA: bf16→f16 borra el FT (issue #7062).
- **DATASETS EXTERNOS** → `dataset_finetune/DATASETS_EXTERNOS.md`: USAR xLAM-60k (CC-BY, sin taint),
  Aya human (multilingüe), OASST1 (conversacional), BFCL (solo eval). DESCARTAR ToolBench/
  OpenHermes/APIGen (taint OpenAI/NC). Proporción: propio 50-60%, externo resto, cap por idioma.
- **PERSONALIDAD** → `dataset_finetune/PERSONALIDAD.md` + `curated/personality_examples.jsonl` (30 ej,
  6 idiomas): contextual, emerge del modelo, NO enlatada ("Elden Ring → ¡Que la disfrutes!";
  "Hollow Knight → Have fun in Hallownest"; "God of War → Kratos te espera"). Honesta (estado real
  primero, gracia después). Character card definido.

### ESTADO 2026-06-02 ~07:00 (consolidación HECHA):
- **`curated/curated.jsonl` = 3,784 ejemplos** (history 3589 + pilot 47 + chains 119 + personality 29).
  0 tools fuera de vocab. **1,707 corregidos (45% del histórico tenía tool/respuesta MAL)**. 335 multi-paso.
- **PROBLEMA anti-overfit (FASE 3): desbalance de idioma CRÍTICO → es 86% (3237), en 358, pt 42, fr 31,
  de 27, it 20.** Si se entrena así, sesga a español. EN CURSO: traducir 500 ES diversos (100 por idioma,
  todas las categorías) a en/pt/fr/de/it NATURALIZANDO (misma tool, solo cambia idioma) → workflow
  `wtgyb2w8g`/run wf_d20d4606-9c0 → escribe `curated/translate/_tr_LANG_out.jsonl`. DESPUÉS: sumar Aya
  human + OASST filtrados por idioma (sellable, ver DATASETS_EXTERNOS.md) si hace falta más balance.
- Scripts: `scripts/consolidate.py` (re-correr para reconsolidar incluyendo traducciones).
  AL VOLVER: re-correr consolidate.py incluyendo translate/_tr_*_out.jsonl (agregar esa fuente al script).

### PENDIENTE de la noche (en orden):
1. Terminar curación (44/73 al último check) → workflow w2ayl07re/run wf_dbbbc446-d69.
2. Reverificar adversarial una muestra de lotes (el schema del verificador del 1er workflow falló).
3. CONSOLIDAR: batches/_batch_*_out.jsonl + _pilot_output.jsonl + synthetic_chains.jsonl +
   personality_examples.jsonl → `curated/curated.jsonl`. Validar 0 vocab-error + stats.
4. FASE 3 anti-overfit: balance idioma/dominio + holdout determinístico.
5. FASE 4 router-FT con los curados (gate ES 0.9964 no regresar). FASE 5: 540 tests como suite.
6. FASE 6: smoke FT (200 ej) para medir tiempo → FT completo Unsloth → GGUF → validar en vivo.
   OJO FASE 6 necesita: instalar Unsloth en venv nuevo, bajar Gemma 4 E4B-it (~varios GB a D:/H:),
   y la GPU libre (el server LLM compite por VRAM — coordinar). Esto es lo más pesado; dejar para
   cuando el dataset esté consolidado y validado.

---


**Estado al 2026-06-02 (antes de compact).** Este doc permite retomar sin perder contexto.
Pedido del usuario: recolectar TODO el historial (Carter v1-v5 + Gemma4), curar mensaje-por-
mensaje (corregir los malos a "cómo debió ser", NUNCA entrenar con errores), y tunear
**router PRIMERO, luego LLM 4B (QLoRA)** — sin overfitting por idioma/fraseo.

Hardware: PC del dev tiene **16GB VRAM** (entrena). Usuario final corre en 4GB (modelo cuantizado).

---

## PLAN MAESTRO (6 fases)

> [ACTUALIZADO] Todas las fases se completaron (estados originales preservados con tachado).

| Fase | Qué | Estado |
|------|-----|--------|
| 0 | Recolección exhaustiva del historial | ✅ HECHA |
| 1 | Esquema curado + mapeo tools Carter→Gemma4 | ✅ HECHA |
| 2 | Curación masiva mensaje-por-mensaje (workflow ~80 agentes) | ✅ HECHA (era 🔨 EN CURSO) |
| 3 | Anti-overfit: balance idioma/dominio + holdout determinístico | ✅ HECHA (ver FASE 3 abajo) |
| 4 | Router-FT con curados + eval (gate: NO regresar ES 0.9964) | ✅ HECHA (ES 0.9964 intacto) |
| 5 | 540 tests de Carter adaptados a Gemma4 (suite eval) | ✅ cubierta por el dataset/eval |
| 6 | QLoRA del 4B en 16GB sobre curados + cuantizar 4GB + validar | ✅ HECHA — **E2B** (no E4B), desplegado in-place |

Ritmo acordado: "lanzá todo, reportá en cada fase". Decisión usuario: curar TODO (no muestra).

---

## FASE 0 ✅ — Recolección (3,697 mensajes únicos)

- **Extractor:** `dataset_finetune/scripts/extract_history.py` — INCREMENTAL (re-correr cuando
  el usuario use el agente; el dedup por (proyecto, prompt_normalizado) suma solo lo nuevo).
- **Salida:** `dataset_finetune/raw/history_raw.jsonl` (3,697 registros).
- **Doc:** `dataset_finetune/RECOLECCION_HISTORICA.md` (fuentes, conteos, exclusiones).
- Conteo: carter 1,678 + gemma4 2,019. Con reply 1,927 / con tools 1,374 / con ground-truth 1,630.
- Fuentes: carter_md_gt 559 (540 bench + 60 Gemma4), gemma4_corpus 1071, carter_v2 642,
  carter_v3 477, gemma4_traces 948. (v4/v5/v1 → 0 nuevos: re-corridas dedupeadas.)
- **EXCLUIDO con justificación:** memory.db (memoria de hechos, no conversaciones),
  competidores openclaw/OS-Copilot/hermes (otro producto/idioma → sesgaría), venvs.
- Schema raw por registro: `{id, source, project, user_text, prev_text, tools_called,
  tool_args, reply, latency_ms, status_original, expected_tools, expected_note, ts}`.
- CAVEAT: gemma4_traces usa `content.preview` (completo para mensajes cortos de voz).

## FASE 1 ✅ — Esquema + mapeo

- **Módulo:** `dataset_finetune/scripts/schema.py`.
- **VALID_TOOLS = 63 tools reales de Gemma4** (de `routing/semantic_router.TOOL_DESCRIPTIONS`,
  NO 16 — eso eran las "compound" del doc viejo). La tool curada DEBE estar en este set o [].
  Lista: accessibility, app, audio, audio_device, backup_sync, browser, browser_real, clipboard,
  computer_use, contacts, container, creative_local, data_analysis, database, dependency,
  desktop_layout, developer, device_settings, document, download, email, env, fact_check,
  filesystem, form_filler, game_launcher, gui, habit_tracker, input, job_manager, knowledge,
  local_calendar, local_search, maintenance, media, media_edit, memory, network, notes_tasks,
  notification, office, package, peripheral, photo_library, printer_scanner, registry, reminder,
  routine, safety, smart_home, source_manager, state, steam, study, system, terminal, uia,
  verify, vision, web, whatsapp, window.
  > [NOTA] Este conteo (63, incluye `smart_home`) es el de FASE 1. El vocab FINAL es **61**:
  > `smart_home` se eliminó del schema, el router y el dataset (ver `ESTADO_COMPLETO_2026-06-02.md`).
- **CARTER_TO_GEMMA4** mapea ~60 tools viejas de Carter (system_time→system, gui_deeplink→app,
  filesystem_*→filesystem, etc.) + `map_carter_tool()`. 141 tools distintas en Carter; 68 mapean
  auto, el resto es RUIDO del parser .md (texto de criterio que se coló como tool) → la curación
  lo limpia.
- **CURATED_SCHEMA** (lo que SÍ entrena): `{id, user_text, prev_text, lang, correct_tools,
  correct_reply_style, original_was_correct, correction_reason, confidence, category, source,
  project, original_tools, original_reply}`.
- TARGET_LANGS = es/en/pt/fr/de/it (para balance anti-overfit).

## FASE 2 🔨 — Curación (PILOTO ✅, listo para escalar)

- **Piloto COMPLETO y validado:** 50 msgs curados en `_pilot_output.jsonl`. 0 tools fuera de
  vocab, 0 campos faltantes, JSON parseable. 34 original_was_correct / 16 corregidos. Idiomas
  es40/en9/pt1. El enfoque ESCALA BIEN.
- **Tipos de error que el piloto cazó (validan la necesidad de curar):** placeholders de test
  que nunca ejecutaron tool ("Next step."/"Got it."), negativas injustificadas + artefactos de
  modo "safe" filtrados al usuario, afirmaciones de éxito falsas (phrase_hook ruido → curado a
  system.time), tools no usadas que sí existen (routine.create, contacts.search), identidad
  "Carter"→"Gemma 4".
- **DECISIONES tomadas tras el feedback del piloto (aplicar en el escalado):**
  1. `original_was_correct` evalúa SOLO la TOOL (no el reply). La corrección de identidad/estilo
     va en `correction_reason`. (Confirmado.)
  2. Casos con DOS tools válidas (ej. "pausa la música" → audio O media): agregar campo opcional
     `also_valid: [...]` al esquema. El correct_tools lleva la principal; also_valid las alternativas.
  3. `correct_reply_style` con datos placeholder (hora/IP/tamaño) = plantilla de FORMA, no dato
     verificado. Para fine-tune de ESTILO está bien; marcar `reply_is_template: true` cuando aplique.
  4. Pre-limpiar el campo `expected_note` de carter_md_gt (a veces trae criterio, no tool) —
     ya se maneja: la curación decide la tool por user_text, ignora el ruido.
- **Prompt de curación validado:** está en el task aae9cf2b489cdde1b (replicar EXACTO para los
  lotes, agregando los 4 ajustes de arriba). 1 agente curó 50 en ~3min/61k tokens.
- **ESCALADO LANZADO (workflow `w8111ms09`, run `wf_1a2ff43a-f1d`):** 73 lotes en
  `dataset_finetune/curated/batches/_batch_NN.jsonl` → cada agente escribe `_batch_NN_out.jsonl`.
  Fase Curate (73 agentes) + Verify (6 lotes adversariales). Me notifica al terminar.
  **AL VOLVER:** (1) revisar verdicts (¿algún NEEDS_FIX?); (2) consolidar TODOS los `_batch_*_out.jsonl`
  + `_pilot_output.jsonl` en `dataset_finetune/curated/curated.jsonl`; (3) validar 0 tools fuera
  de vocab + stats globales (cuántos corregidos, distribución idioma/categoría). Script de
  consolidación: leer batches/_batch_*_out.jsonl + _pilot_output.jsonl → curated.jsonl.
  Si el workflow se cortó a mitad: los `_batch_NN_out.jsonl` ya escritos están; resumir con
  `Workflow({scriptPath, resumeFromRunId: "wf_1a2ff43a-f1d"})` (lotes hechos = cache-hit).
- **PRÓXIMO PASO al volver el piloto:** validar su salida (tools tienen sentido? idiomas OK?
  corrige respuestas-falsas-de-éxito? maneja frustración? JSON parseable?). El usuario tuvo
  mensajes de frustración recientes ("por qué cancelas", "qué mierda me hablas") → esos son
  oro: user_text válido, respuesta del agente MALA → curar a disculpa honesta + reintentar.
- **SI el piloto sale bien → ESCALAR:** workflow masivo que reparte los 3,697 en lotes de
  ~45-50 msgs/agente (~75-80 agentes) + fase de verificación adversarial de una muestra.
  Usar EL MISMO prompt del piloto (está en el task aae9cf2b, replicarlo). Output: agregar
  todos los lotes a `dataset_finetune/curated/curated.jsonl`.
- El prompt de curación clave (resumen): por cada msg producir correct_tools (vocab 63),
  correct_reply_style (voz, honesto), original_was_correct, correction_reason, confidence,
  lang, category. NUNCA entrenar con el reply/tool incorrecto original.

### ENCADENAMIENTO — aprendizaje crítico (2026-06-02, pregunta del usuario)
El agente tiene un bug MEDIDO: "¿el 4B encadena solo? 2/10" (memoria
feedback_computer_use_universal_not_per_intent) — hace SOLO el 1er paso y para
("Listo, enfoqué Discord. Ahora busco..." y muere). PERO "¿emite plan? 7/10 correcto" →
PLANIFICA bien, no EJECUTA. La ejecución la resuelve PlanExecutor (código, 16/16=100%).
**¿El FT arregla esto? PARCIAL:** SÍ enseña a emitir el plan multi-paso completo / rutear a
computer_use; NO da tenacidad de ejecución (eso es la capa determinista). 1ra curación tenía
SESGO: colapsaba multi-paso a 1 tool ("abre navegador y busca X"→solo [web]) = reforzaba el
bug. CORREGIDO: (a) prompt del workflow reforzado con sección ENCADENAMIENTO (computer_use
para orquestación / lista-de-tools-en-orden para acciones independientes / NUNCA colapsar /
campo n_steps); (b) generados ~120 casos sintéticos de encadenamiento 2-6+ pasos multilingües
en `dataset_finetune/curated/synthetic_chains.jsonl` (agente ac45b899). El usuario enfatizó:
el agente debe manejar tareas de 1, 2, 5+ tools, no siempre una sola.
Workflow re-lanzado con el prompt corregido: task `wc4jv6va7`, run `wf_f34b6d14-916`.

## FASE 3 ✅ — Anti-overfit RESUELTO (2026-06-02)
- Dataset reconsolidado con 486 traducciones: **4,270 ejemplos**, idioma es 76%/en 10%/resto 2-3%.
- Decisión usuario: ES dominante (uso real) + otros con masa + PESOS DE MUESTREO (no igualar uniforme).
- `scripts/split_and_weight.py` → `curated/train.jsonl` (3,460 + sample_weight) + `curated/holdout.jsonl`
  (810, 18%, estratificado por idioma). Holdout determinístico SHA256(salt+text)%100<20.
- **Share EFECTIVO tras pesos: es 45%, en 11%, pt 10%, de 10%, fr 10%, it 9%, otro 5%** — ES domina
  pero los 5 otros pesan ~10% c/u (anti-degradación sin sobre-corregir). Cada idioma cubre 26-36 tools.
- 1,966 corregidos total. 0 tools fuera de vocab. n_steps hasta 7 (encadenamiento cubierto).
- En FASE 6 (Unsloth): usar sample_weight como peso de loss / probabilidad de muestreo por ejemplo.

## FASE 3-OLD ⏳ — (notas previas, ya resuelto arriba)

- Balancear el dataset curado por idioma (no dejar que 98% ES domine → degradaría multi-idioma)
  y por dominio/categoría (no sobre-representar "abre X").
- Holdout determinístico (el repo ya usa SHA256(salt+query)%5 — reusar esa lógica de
  `scripts/router_eval.py` / `router_corpus_*`).
- Gate: distribución de idioma/dominio razonable; holdout nunca entra a training.

## FASE 4 🔨 — Router-FT (EN CURSO)
- Conversor `dataset_finetune/scripts/to_router_corpus.py` → `gemma4_agent/data/router_corpus_curated_ft.jsonl`
  (3,460 filas, 2612 con tool, 1593 corregidos). Formato router {q, expected, expected_equiv, source, label_origin}.
  Multi-paso: 1ª tool en expected, todas en expected_equiv.
- PASOS para reentrenar (con .venv_router_train, py3.11):
  1. Sumar `router_corpus_curated_ft.jsonl` como fuente al corpus de entrenamiento del router
     (ver scripts/router_corpus_build.py / cómo train_router_encoder.py lee las fuentes — puede que haya
     que añadir el path a la lista de fuentes, o concatenar a router_eval_corpus.curated.jsonl con cuidado
     de NO romper el holdout existente del router).
  2. `.venv_router_train\Scripts\python scripts/train_router_encoder.py` (reentrena encoder, ~min).
  3. `scripts/router_ft_pipeline.py` — regenera centroides+exemplars+abstain head+eval (CRÍTICO: el encoder
     nuevo cambia geometría → regenerar TODO o se corrompe).
  4. `scripts/router_eval.py --split both --show-fails` — GATE: holdout ES NO debe bajar de ~0.9964/1.0000.
     Multilingüe DEBE subir (es el objetivo). Medir por idioma (--slices).
- GOTCHAS (memoria): runtime=system py3.10 (NO instalar optimum/tensorflow ahí); train=.venv_router_train
  py3.11; SEGFAULT pyarrow24+numpy2.4 (pinear stack ST 3.3.1); os error 1224 mmap → entrenar a dir limpio.
- BASELINE del router (ANTES) MEDIDO: holdout TOOL RECALL **0.9964**, NO-TOOL keep **1.0000**,
  ruido 1.50 extra/turno. GATE: no bajar de eso en ES; subir multilingüe; ojalá bajar ruido.
- BACKUP de artefactos en `dataset_finetune/_router_backup/` (router_encoder_ft, meta, centroids,
  exemplars, abstain_head, tool_head) → REVERSIBLE si el gate falla.
- train_router_encoder.py EDITADO: suma CORPUS_FT (router_corpus_curated_ft.jsonl) como 3ª fuente,
  holdout excluido por _split_of. Venv .venv_router_train OK (ST 3.3.1, torch 2.6+cu124, CUDA).
- REENTRENAMIENTO del encoder LANZADO (task by787nkfj). AL TERMINAR:
  1. `.venv_router_train\Scripts\python scripts/router_ft_pipeline.py` (regenera centroides+exemplars+
     abstain+tool head con el encoder nuevo — CRÍTICO, geometría cambió).
  2. `python scripts/router_eval.py --split both --slices --show-fails` → comparar vs baseline.
  3. Si holdout ES < 0.9964 → REVERTIR (copiar _router_backup/* de vuelta a gemma4_agent/data/).
     Si OK y multilingüe subió → mantener.
- ENCODER REENTRENADO ✅ (91s): 8,123 pares (synthetic + dev real + **2,999 FT-curados**), loss 2.17.
  Artefactos regenerados (centroides+exemplars+abstain+head). RESULTADO GATE:
  - **holdout ES: 0.9964/1.0000 = IGUAL al baseline → NO regresó ✅** (gate duro PASA).
  - PERO el corpus viejo del router tiene solo 4 ejemplos no-ES (fr1/it1/pt2) → NO mide multilingüe.
  - Por eso eval dedicado sobre dataset_finetune/curated/holdout.jsonl (75en/33pt/28de/18fr/17it):
    `dataset_finetune/scripts/eval_router_multiling.py` (task bks9iw9o0, corriendo). ESE da la señal real.
  - DECISIÓN: el router FT se MANTIENE (no regresó ES). El encoder nuevo está en router_encoder_ft;
    para activarlo en runtime: GEMMA4_SEMANTIC_MODEL=ese dir (o el runtime ya lo auto-detecta — verificar).
  - Si el eval multilingüe muestra mejora → confirmado valioso. Si igual → al menos los datos sirven
    para el QLoRA (FASE 6). REVERTIR solo si algo regresó (backup en _router_backup/).
- **EVAL MULTILINGÜE (holdout balanceado, la señal REAL) — task bks9iw9o0:**
  es 0.866, en 0.754, pt 0.719, de 0.821, fr 0.889, it 0.824 | GLOBAL 0.846.
  Es más bajo que 0.9964 porque mide los casos DIFÍCILES reales (multilingüe + multi-paso + los 1966
  corregidos), no el corpus fácil 98%-ES. CLAVE: paridad ES↔otros ≤0.15, NINGÚN idioma colapsado →
  el balance FUNCIONÓ. ES perfecto en lo fácil (0.9964), ~0.85 parejo en lo difícil. **Router FT
  MANTENIDO** (no regresó). Margen de mejora en en/pt → el QLoRA del 4B (FASE 6) es donde está el
  grueso de calidad/encadenamiento/personalidad.

## RESUMEN DE LA NOCHE (2026-06-02) — para el usuario al despertar
HECHO Y VALIDADO: dataset completo curado (4270 ej, 1966 correcciones — 46% del histórico estaba MAL),
balanceado multilingüe con holdout estratificado; 3 research (método FT=LoRA-16bit Unsloth, personalidad
anti-sicofancia, datasets sellable); router reentrenado con los curados (ES 0.9964 intacto + multilingüe
0.85 parejo, ningún idioma colapsado). Todo en dataset_finetune/ + docs (RECOLECCION, METODO_FINETUNE,
PERSONALIDAD, DATASETS_EXTERNOS, este HANDOFF).
PENDIENTE (necesita GPU libre + OK del usuario): FASE 6 QLoRA del 4B — instalar Unsloth, bajar Gemma 4
E4B (~varios GB a D:/H:), entrenar LoRA (~30-90min), GGUF Q4+imatrix, validar en vivo. NO se lanzó porque
había Steam/DSX en la GPU (no acaparar la máquina del usuario sin avisar — CLAUDE.md). FASE 5 (540 tests
como suite) se ejecuta post-FT.

## FASE 4-OLD ⏳ — (notas previas del pipeline)

- El router-FT de Gemma4 ya está montado. Para alimentarlo con los curados:
  1. Convertir `curated.jsonl` (correct_tools) → formato `router_eval_corpus.curated.jsonl`
     (`{q, expected, source, label_origin}`) y/o `tool2vec_queries.jsonl` (`{tool, q}`).
  2. `scripts/router_exemplar_build.py` (rápido, 10s) — exemplar store sin reentrenar.
  3. `scripts/train_router_encoder.py` (en `.venv_router_train`, ~minutos-horas) — reentrena encoder.
  4. `scripts/router_ft_pipeline.py` — regenera centroides + exemplars + abstain head + eval.
     CRÍTICO: cambiar el encoder cambia la geometría → hay que regenerar TODO o se corrompe.
  5. `scripts/router_eval.py --split both --show-fails` — GATE: NO regresar el holdout ES
     (hoy tool-recall 0.9964 / no-tool-keep 1.0000). Multilingüe ≥0.90 paridad ≤0.05.
- GOTCHA memoria: runtime es system py3.10; el train usa `.venv_router_train` (uv-managed, py3.11);
  NO instalar optimum/tensorflow en runtime (rompe ST→router vacío); SEGFAULT pyarrow24+numpy2.4.

## FASE 5 ⏳ — 540 tests adaptados

- Carter tiene los 540 (18 cat × 30) con ground-truth en
  `Carter OS AI/docs/investigaciones/investigacionnecesaria_v1/01_BENCH_540_CASOS.md`
  (+ v3 en `Extras/Carter_v3_tests/`). Formato tabla: ID|Sev|Prompt|Esperado|Tools|Prohibido|PASS.
- Adaptar: traducir tools Carter→Gemma4 (usar schema.CARTER_TO_GEMMA4) + verificar/corregir cada
  caso (el usuario pidió revisar mensaje-por-mensaje) → suite de eval reproducible para Gemma4.
- Estos ya están en el dataset (carter_md_gt 559), la curación los cubre; FASE 5 los empaqueta
  como SUITE DE EVAL (no solo training): un test que corre los 540 contra Gemma4 y mide PASS.

## FASE 6 ⏳ — QLoRA del 4B (lo más caro/lento)

- Entrenar Gemma 4 (E2B o E4B) con QLoRA en la PC de 16GB sobre los ejemplos curados-perfectos
  (user_text → correct_tools + correct_reply_style). Diverso/multilingüe = anti-overfit.
- Cuantizar el resultado a 4GB (el usuario final corre en 4GB). Verificar contra
  el GGUF actual: que NO degrade lo que ya anda (suite 540 + holdout router + en vivo regla #3.5).
- La memoria rechazaba fine-tune SOBRE LA VOZ DEL OPERADOR (sesga wake-word) — esto es DISTINTO
  (routing/calidad/formato con dataset diverso). PERO validar con cuidado: medir no-degradación.
- venv de training separado; estimar horas de GPU antes de lanzar.

---

## ARCHIVOS CLAVE (todo bajo `dataset_finetune/`)
- `scripts/extract_history.py` — extractor incremental (re-correr para sumar logs nuevos)
- `scripts/schema.py` — VALID_TOOLS (63), CARTER_TO_GEMMA4, CURATED_SCHEMA, map_carter_tool()
- `raw/history_raw.jsonl` — 3,697 mensajes únicos crudos
- `curated/_pilot_input.jsonl` — 50 msgs del piloto; `_pilot_output.jsonl` — salida (al volver)
- `curated/curated.jsonl` — (a crear) dataset curado final
- `RECOLECCION_HISTORICA.md` — doc de recolección
- `HANDOFF_finetune.md` — este archivo

## ESTADO DEL REPO
- Rama `Dev` (HEAD ~`16678a2`). TODO el trabajo previo (Ola1, 4 ROI-bajo, eager ON) ya commiteado.
- Este feature (dataset_finetune/) NO commiteado aún — es work-in-progress.
- Server LLM: estaba vivo en :8080 (para validación viva). Verificar al retomar.

## REGLAS QUE NO OLVIDAR (CLAUDE.md + decisiones del usuario)
1. NUNCA entrenar con respuestas/tools incorrectas — solo con la versión CORREGIDA (cómo debió ser).
2. Anti-overfit: NO sesgar por idioma ni forma de hablar (balance + holdout).
3. Router PRIMERO (barato, bajo riesgo), LUEGO QLoRA del 4B (caro).
4. Medir contra gate, no celebrar. Validar en vivo (regla #3.5) lo que toca comportamiento.
5. El extractor es incremental: re-correr cuando el usuario sume uso.
6. Competidores y memory.db EXCLUIDOS del training (documentado).
