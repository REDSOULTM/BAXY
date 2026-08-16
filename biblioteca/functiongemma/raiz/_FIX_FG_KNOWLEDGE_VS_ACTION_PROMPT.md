# PROMPT/HANDOFF — Arreglar el mis-route conocimiento→acción de FunctionGemma

**Para:** el agente que trabaje en el repo FunctionGemma (`C:\Users\usuario\Desktop\ETC\
Programacion\FunctionGemma\`). **Origen:** integración de FunctionGemma run9 como router de
tool-calling en Baxy (repo `Probando Gemma 4`, rama `Experimentando`), 2026-06-17.
**Objetivo:** subir la accuracy de abstención/ruteo de FunctionGemma para que NO mande queries
de CONOCIMIENTO/CONVERSACIÓN a tools de ACCIÓN. Es el único blocker para hacer default el
perfil lean (`vram4_lean`) en Baxy.

---

## 1) El problema (medido en vivo)

FunctionGemma (270M, run9) integrado en Baxy funciona bien en la mayoría de los casos
(abstención no_tool 3/3 en chitchat, rescate multilingüe de acciones), PERO **mis-rutea un
long-tail de queries de CONOCIMIENTO/abiertas a tools de ACCIÓN**. El modelo de habla (E2B)
entonces narra el resultado espurio de esa tool → parece que "confabula" / describe pantallas.

**Casos MEDIDOS (vía el agente real de Baxy, FG router on):**
- `"what is a linked list"` → FG ruteó a **vision** → el agente capturó la pantalla y respondió
  *"Listo, capturé la pantalla con vision y te la describo"* (en vez de explicar qué es una lista enlazada).
- `"contame de roma"` (= contame DE Roma, la ciudad) → FG ruteó a **contacts** (tomó "Roma" como
  nombre de contacto) → *"Aquí están los contactos de Roma"*.
- `"y cuánto mide?"` (multi-turno sobre la torre Eiffel) → FG ruteó a **data_analysis**
  `{action: csv_describe, path: datos.csv}` (inventó un CSV).
- En aislado (`fg_emit`, e2b_emitted=False) varias de estas SÍ daban `no_tool` correctamente
  ("contame de roma"→no_tool, "torre eiffel"→no_tool) — el mis-route aparece sobre todo cuando
  el gate marca "accionable" por OTRA señal (ver §2) y FG, forzado a elegir del subset, agarra
  la tool equivocada.

**Impacto:** en queries de conocimiento ("qué es X", "contame de Y", "quién fue Z", multi-turno
factual), ~1 de cada 3-4 termina disparando una acción espuria (vision/contacts/data_analysis/
click). Es UX inaceptable para hacer el split default. NO es alucinación del modelo de habla
(el FT Q4_K_M narra bien cuando NO se dispara tool); es la accuracy del router de 270M.

---

## 2) Cómo está armado el ruteo HOY (contexto para el fix)

Integración en Baxy: `gemma4_agent/routing/fg_router.py`. Flujo por turno:
1. El E2B (habla) corre primero y puede emitir un tool-call.
2. `fg_emit(query, e2b_emitted)` decide el tool-call autoritativo, con un **gate
   acción-vs-conversación** ANTES de llamar a FunctionGemma:
   - `scored = suggest_tools_scored(query, k=12)` (encoder MiniLM-L12-FT multilingüe de Baxy).
   - **act = (encoder top-1 de familia ≥ FG_ACT_PEAK=0.52) OR e2b_emitted.**
   - Si NO act → `no_tool` (no se llama a FunctionGemma; responde el E2B).
   - Si act → router jerárquico (familias→hijos del `tool_categories.json`)→ top-K + `no_tool`
     SIEMPRE en el subset → FunctionGemma elige.
3. Bridge individual→compuesto (reverse `tool_action_map.json`) → ToolRegistry de Baxy.

**Dónde se cuela el mis-route:**
- (a) El **gate es permisivo** para conocimiento: queries como "what is a linked list" /
  "contame de roma" pueden tener encoder top-1 ≥0.52 (caen cerca de familias web/knowledge/
  contacts) → el gate dice "act".
- (b) Una vez en "act", **FunctionGemma DEBE elegir del subset** y, en el long-tail, agarra una
  tool de acción tentadora (vision/contacts/data_analysis) en vez de `no_tool`. Es el eager-
  invocation clásico de SLMs (SimpleToolHalluBench arXiv 2510.22977, When2Call arXiv 2504.18851),
  pero ahora en queries de CONOCIMIENTO, no chitchat.
- El `no_tool` SÍ está siempre en el subset (fix previo), y FG abstiene bien en chitchat puro;
  el problema es el conocimiento que "parece accionable" por el encoder.

---

## 3) El fix pedido: clasificador CONOCIMIENTO-vs-ACCIÓN antes de FunctionGemma

La idea (del dueño del proyecto): **un clasificador conocimiento-vs-acción que corra ANTES de
FunctionGemma** y, si el turno es de CONOCIMIENTO/CONVERSACIÓN, devuelva `no_tool` sin siquiera
consultar a FG. Solo turnos genuinamente ACCIONABLES (control del SO, apps, mensajería, media,
archivos, etc.) pasan a FunctionGemma.

**Restricciones de Baxy (CLAUDE.md — son ley, respetarlas en el diseño):**
- **NADA de listas de keywords/apps/URLs por idioma** ni hardcodes. Lo permitido: clasificación
  por **embeddings multilingües con fallback seguro**, o **guardas estructurales** que miden la
  FORMA. Universal, multi-idioma (es/en/fr/pt/it/… 25 idiomas como Parakeet).
- Sub-milisegundo / barato (corre en CPU en cada turno de voz; budget de latencia 4-5s total).
- Reproducible: pesos en artefacto versionado (JSON/npz), regenerable por script.

**Enfoques candidatos (a evaluar/medir, no asumir):**
1. **Cabeza calibrada conocimiento-vs-acción** sobre los embeddings del encoder (estilo el
   `abstain_head` que Baxy ya tiene en `gemma4_agent/safety_pkg/abstain_head.py`): regresión
   logística sobre features baratas (cosenos a centroides de intent + forma del top-k + longitud
   + ¿es pregunta?). Entrenada offline con dataset balanceado conocimiento/acción multilingüe.
   Es el camino más alineado con lo que ya existe. OJO: el abstain_head actual con intent=None NO
   separa esto (mide chitchat-vs-tool, no conocimiento-vs-acción); habría que entrenar features
   con los centroides de intent ACTIVOS (info/action/chitchat) o un head dedicado.
2. **Mejorar la abstención de FunctionGemma con datos contrastivos de CONOCIMIENTO**: agregar al
   trainset de FG ejemplos de queries de conocimiento ("qué es X", "contame de Y", "quién fue Z",
   "cuánto mide", multi-turno factual) en 25 idiomas con target `no_tool`, para que FG aprenda a
   abstenerse en conocimiento aunque el subset tenga tools tentadoras. (Reusar el pipeline
   `finetune_llm/build_fg_trainset.py` + `train_fg.py`; ya hay handcrafted batches en `curated/hc/`.)
3. **Endurecer el gate**: subir FG_ACT_PEAK o requerir DOS señales (encoder peak AND e2b_emitted)
   para queries que matchean la familia "info/web/knowledge". Más simple pero menos preciso;
   puede perder acciones legítimas con bajo peak.

**Recomendado:** combinar (1)+(2) — un clasificador conocimiento-vs-acción calibrado (1) como
gate barato, respaldado por FG entrenado para abstener en conocimiento (2) como red de seguridad.
El (1) decide rápido sin invocar FG; el (2) endurece a FG para el caso en que el gate se equivoca.

---

## 4) Cómo medir (gate de éxito — definirlo ANTES)

- Dataset de evaluación: queries de CONOCIMIENTO (objetivo no_tool) + queries de ACCIÓN
  (objetivo: la tool correcta), balanceado, multi-idioma. Reusar/extender el `fg_holdout` y los
  canarios. Métricas: **% conocimiento→no_tool** (subir de ~70% a ≥95%) SIN bajar **% acción→tool
  correcta** (mantener ≥90% multilingüe, el gate del split).
- Harness en vivo en Baxy (regla 3.5): `scripts/_recheck_vision_confab.py` y
  `scripts/_validate_lean_broad.py` ya prueban end-to-end que queries de conocimiento NO disparen
  vision/contacts/etc. Correrlos contra el FT-lean (vram4_lean) con el fix aplicado → objetivo
  0/N confabs.
- No-regresión: el `router_canary_eval.py` de Baxy (45-46/63 hoy; no bajar) + las acciones
  multilingües (es/en/fr/pt/it) que YA andan no deben romperse.

## 5) Artefactos/refs en el repo FunctionGemma
- `INTEGRATION_HANDOFF.md` (contrato de runtime + el fix de router no_tool ya hecho).
- `fg_router_ft.py` (router jerárquico de referencia), `tool_schemas_slim.json` (525 tools incl
  no_tool), `tool_categories.json`, `finetune_llm/` (build/train/eval + curated/ con handcrafted).
- En Baxy: `gemma4_agent/routing/fg_router.py` (gate actual + FG_ACT_PEAK), `semantic_router.py`
  (encoder + suggest_tools_scored), `safety_pkg/abstain_head.py` (el patrón de head calibrado).

## 6) Estado actual (lo que NO hay que re-hacer)
- `no_tool` SIEMPRE en el subset: HECHO. Abstención en chitchat puro: OK (3/3 medido).
- Gate acción-vs-conversación por encoder-peak OR e2b_emitted: HECHO (FG_ACT_PEAK=0.52).
- Rescate multilingüe de acciones: OK (es/en/fr/pt/it medido).
- Lo que FALTA y es ESTE prompt: la capa conocimiento-vs-acción para cortar el long-tail de
  conocimiento→acción ANTES de (o dentro de) FunctionGemma.
