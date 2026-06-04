# Estado completo del Fine-Tuning Gemma 4 E2B — 2026-06-02

Documento maestro anti-compact. Captura TODO el estado para retomar sin perder contexto.

> **ACTUALIZACIÓN DE ESTADO (registrada al revisar la doc):** el **deploy IN-PLACE
> YA SE HIZO** (lo que este doc listaba como "PENDIENTE" se completó esa misma noche).
> El modelo del fine-tune está desplegado en `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf`
> (3.4 GB on-disk, verificado) con el base original respaldado en
> `models/E2B/gemma-4-E2B-it-Q4_K_M.BASE-BACKUP.gguf` (3.1 GB) + `mmproj-F16.gguf` (985 MB).
> Producto = **Baxy** (el MODELO sigue siendo Gemma 4). Las secciones de abajo se
> conservan como registro histórico del cierre del FT; los pendientes están al final
> con su estado real. Detalle del deploy en `MISION_COMPLETA_HANDOFF.md`.

---

## RESUMEN EJECUTIVO

Se fine-tuneó **Gemma 4 E2B** (NO E4B) para un asistente de voz local (**Baxy**) que debe
correr en **4GB de VRAM**. El E4B se descartó (no entra en 4GB). El modelo final v2 está
entrenado sobre un dataset **certificado 100% limpio**, pasó el gate (0% tools inventadas
en prod), entra en 4GB (2.07GB VRAM), y **YA está desplegado in-place** (ver banner arriba).
PENDIENTE al cierre original: validación ampliada (corriendo) y minimización de prompts.
[El deploy, que figuraba aquí como pendiente, está COMPLETADO.]

---

## ARTEFACTOS FINALES (rutas absolutas)

- **Modelo LLM final:** `dataset_finetune/out/gemma4-E2B-ft-Q4_K_M.gguf` (3.2GB, entra en 4GB)
  - merged-bf16 en `dataset_finetune/out/merged-bf16/` (9.6GB)
  - LoRA en `dataset_finetune/out/lora/`
  - imatrix multilingüe en `dataset_finetune/out/imatrix.dat`
- **Router v2 (ya en runtime, auto-detectado):**
  - encoder FT: `gemma4_agent/data/router_encoder_ft/`
  - `gemma4_agent/data/{abstain_head.json (thr 0.68), tool2vec_centroids.npz, router_exemplars.npz, tool_head.json}`
  - backup pre-cambio: `dataset_finetune/_router_backup_pre_e2b/`
- **Modelo de PROD:** `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf` + `mmproj-F16.gguf`.
  [ACTUALIZADO: el .gguf de PROD **ya es el fine-tune** (deploy in-place hecho, 3.4 GB
  on-disk). Base original respaldado en `gemma-4-E2B-it-Q4_K_M.BASE-BACKUP.gguf` (3.1 GB).
  Revertir = copiar el .BASE-BACKUP sobre el .gguf.]
- **Base HF entrenable:** `dataset_finetune/base_model/gemma-4-E2B-it/` (9.6GB, con chat_template.jinja)

## DATASET (certificado 100% limpio)

- `dataset_finetune/curated/curated.jsonl` (6661) → `train.jsonl` (5381) + `holdout.jsonl` (1280)
- Composición: dominio histórico curado (carter v1-v6 + gemma4) + 329 conversación pura
  (it/pt/fr/de para romper sesgo idioma→tool) + 346 cobertura de tools (las 61) +
  155 flujos multi-paso + externos Aya 553 + OASST 288 (conversacionales, 0-tool).
- Campos clave: correct_tools, also_valid, n_steps, correct_reply_style, reply_is_template,
  mode (normal/movilidad/no_vidente), tool_args, category, lang, source.
- **smart_home ELIMINADA** (schema tool_schemas.py + VALID_TOOLS schema.py:24 + todos los
  artefactos del router + dataset). VALID_TOOLS = 61 tools.

## BUGS ENCONTRADOS Y ARREGLADOS (la auditoría de 6 agentes los cazó)

1. **Serialización:** 393 ejemplos con tools como string anidado `"['media']"` en
   correct_tools/also_valid (de carter_v3/traces/corpus/traducidos) → des-serializados.
   Script: `dataset_finetune/scripts/_fix_tool_serialization.py`.
2. **Acciones inválidas en tool_args:** `developer.start_dev`→`start_dev_server`,
   `printer_scanner.cancel`→`cancel_job`. Script: `_fix_audit_blockers.py`.
3. **Replies con slots sin marcar:** ~63 con placeholders `[saved name]/[ruta]/(fecha)/
   [color guardado]/<descripcion>` (incl. uno francés de 64 chars que escapó al regex de 60)
   → marcados reply_is_template=True. Scripts: `_fix_audit_blockers.py`, `_fix_slots_v2.py`.
   Total reply_is_template marcados: 608 train + 154 holdout.
- **Certificación final:** OOV=0, serializados=0, smart_home=0, inventadas=0, slots=0,
  bad_act=0, fugas=0, contradicciones=0 (train + holdout).

## RESULTADOS MEDIDOS

### LLM E2B-FT v2
- train_loss 0.48 (SANO, NO overfit — el E4B bajó a 0.09=sobreajuste). 63min, VRAM peak 15.6GB.
- **GATE v2 (condiciones PROD = con array tools + parse_tool_calls):** 40/40 en vocab,
  **0% tools inventadas** (vs 35% del v1 con datos sucios). El fix de datos FUNCIONÓ.
- CAVEAT medición: SIN el array de tools el modelo inventa 47% (web_search/google_search/ls).
  Pero PROD SIEMPRE pasa el array (llm_client.py + parse_tool_calls=true) → 0% real. Mismo
  patrón verificado antes en el E4B. NO medir sin el array (no es la config de prod).
- "jajaja"→no dispara tool + responde charlando (over-firing arreglado por el balance).
- app/whatsapp/system correctos en casos clave.
- **VRAM real medida (build 9090): 2.07GB** (1416 modelo + 93 KV + 560 compute, ctx 8k).
  ENTRA en 4GB. Con visión (mmproj 940MB) lazy llega a ~3GB. Comparar: E4B-FT era 5GB (no entraba).

### Router v2 (corpus limpio)
- Global recall 0.846 (=baseline 0.846, =v1). Mejora LATERAL no salto.
- Por idioma: es 0.872↑, en 0.818↑ (baseline 0.754), fr 0.875, it 0.810, de 0.744↓, pt 0.706↓.
- no-tool keep 0.508. smart_home=0. de/pt débiles = dificultad inherente, no el bug.

### Validación ampliada: EN CURSO (task bc33y4akl) → resultados en out/eval/_e2bft_v2_eval.json

## ENTORNO (reproducibilidad)

- `.venv_ft` Python 3.12: unsloth 2026.5.10, torch 2.7.0+cu126, xformers 0.0.30,
  triton-windows 3.3.1, transformers 5.5.0, trl 0.24.0. Page file 64GB (necesario p/cargar 15GB).
- Router se entrena con Python del SISTEMA (torch CPU, NO toca GPU). Gotcha: bloquear
  `sys.modules['tensorflow']=None; sys.modules['tensorboard']=None` (TF roto rompe el callback).
- Pipeline GGUF: convert_hf_to_gguf.py del commit 5757c4dcb (==build 9090 prod) en
  `dataset_finetune/llamacpp_convert/` + gguf 0.19.0. Server estable: `-fa off` (crash CUDA con fa on).
- GOTCHAS: cp1252 (PYTHONIOENCODING=utf-8 + sys.stdout.reconfigure); Dataset.from_list
  rompe con tool_args heterogéneo (construir text en python puro, NO from_list); --chunks 0
  en imatrix = CERO chunks (no usar); device_map={"":0} (no 'auto').

## SCRIPTS CLAVE (dataset_finetune/scripts/)

- Pipeline: extract_history → schema → consolidate → split_and_weight → to_router_corpus →
  train_ft.py (E2B, QLoRA) → quantize_gguf.py → eval_full_dimensions.py
- train_ft.py: BASE_MODEL=base_model/gemma-4-E2B-it, chat_template del modelo, build_messages
  (tool_calls estructurados nativos + args reales + reply_is_template→"Listo."), QLoRA 4bit,
  batch efectivo 16 (4×4), device_map={"":0}, train_on_responses_only marcadores `<|turn>user\n`/`<|turn>model\n`.
- Auditoría: _audit_dataset.py, _fix_tool_serialization.py, _fix_audit_blockers.py, _fix_slots_v2.py.

## PENDIENTE (en orden)

> **NOTA DE CIERRE (revisión de doc):** los ítems 3 (deploy), 4 (handler smart_home) y 5
> (validación en vivo) **se COMPLETARON** esa misma noche — ver `MISION_COMPLETA_HANDOFF.md`
> ("CIERRE POST-COMPACT": deploy in-place confirmado por hash, smart_home limpiado de código
> + handler/refs, validación en vivo hecha que además cazó 2 bugs). El ítem 1 (validación
> ampliada) terminó: recall 0.747 global, pt 0.50 débil, 0/195 tools inventadas (ver
> `MISION_COMPLETA_HANDOFF.md` §"ESTADO DEL MODELO"). El ítem 2 (minimización de prompts)
> avanzó parcialmente (leans + skills + microagents comprimidos; tool_schemas PHASE-2 medido
> y RECHAZADO por ya estar óptimo). Lo de abajo se conserva como el plan original.

1. ~~**Validación ampliada** (corriendo)~~ → [COMPLETADO] recall por idioma medido (ver banner).
2. **Minimización de 74 prompts** (objetivo del usuario): comprimir cada prompt al máximo
   VALIDANDO EN VIVO contra el E2B-FT v2 (regla #3.5). Workflows previos concluyeron:
   - El prompt YA cabe en 8k (path V3 real ~4.2k always-on, no los 9.2k del comentario viejo).
   - Único lever grande verificado: extender .lean.md a 20-25 tools (-1200/1800 tok).
   - PROHIBIDO comprimir guardas (purchase-guard, anti-verifier-storm) sin validación viva.
   - skills_autoinject tiene BUG: computa embed y DESCARTA su output en V3 (arreglar, no extender).
   - RECOMENDADO seguro: bajar ctx 16384→12288 (libera VRAM, 0 riesgo de comportamiento).
3. ~~**Deploy in-place:**~~ [COMPLETADO] el FT reemplazó `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf`
   (parity de chat_template automática: prod usa --jinja sin path = template embebido).
   `-fa off` se hereda. Backup del modelo viejo guardado en `...BASE-BACKUP.gguf`.
4. ~~**smart_home handler runtime:**~~ [COMPLETADO] handler + keyword rule del planner + refs
   eliminados (ver `MISION_COMPLETA_HANDOFF.md` "BUG A"); el LLM ahora admite que no tiene
   esa capacidad en vez de mentir (BUG B también arreglado).
5. ~~**Validación en vivo final** (regla #3.5)~~ [COMPLETADO] hecha con `run_content` (server
   vram4, sin SendInput): router-fix + comandos + visión + smart_home-honestidad confirmados;
   cazó 2 bugs serios que la suite no veía.

## DECISIONES PENDIENTES DEL USUARIO

> [RESUELTAS] Ambas se decidieron y ejecutaron:

- ~~¿Desplegar el E2B-FT v2?~~ **SÍ — desplegado in-place.** El router v2 ya está activo.
- ~~El gate pasó pero la validación ampliada dará el recall por idioma definitivo.~~
  Validación ampliada completada (global 0.747; pt 0.50 el más débil; 0/195 tools inventadas).
