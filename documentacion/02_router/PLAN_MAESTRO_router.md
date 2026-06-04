# Plan Maestro — Router de tools al estado máximo (2026-05-29)

> **[ESTADO al 2026-06-04 — leer antes que el plan]** Este es el plan ORIGINAL
> del 2026-05-29 (producto = "Gemma 4 Agent", hoy **Baxy**; el MODELO sigue
> siendo Gemma 4). Se conserva como registro. Avances desde entonces:
> - **SPRINT 0–6 (router mastery):** ejecutados — ver
>   [05_HISTORIAL_SPRINTS](05_HISTORIAL_SPRINTS.md) (S0–S6).
> - **SPRINT 5 (eje D):** el **anti-primacy ordering** se SHIPPEÓ (`b812841`,
>   gate `GEMMA4_ANTIPRIMACY`); el **few-shot turn-specific** y el **prefill
>   `<|tool_call|>`** se DESCARTARON con medición (ver
>   [06_PENDIENTE_Y_NO_FORZADO](06_PENDIENTE_Y_NO_FORZADO.md) A8).
> - **SPRINT 6 (cap=5):** DECIDIDO **no tocar** (norte = menos tools).
> - **Artefactos regenerados 2026-06-02:** encoder FT + cabezas; `smart_home`
>   eliminado → `tool_head` ahora **61 tools** (no 62); abstain head: 12
>   features, bias 1.4445, **threshold 0.69** (no 0.66); encoder meta
>   **n_pairs 8123**. Las cifras de §1.2/§1.3 abajo son del 2026-05-29 y quedaron
>   desfasadas en esos detalles (el holdout **0.9964 sigue vigente**).
> - **PENDIENTE-real:** SPRINT 0–2 (corpus/eval multilingüe) + ruido medido
>   `wants_web_store` / `web→source_manager` (B5/B6 en el doc 06).
>
> Producto de un workflow de 14 agentes que leyó TODO el research de router (9 docs + PDF)
> + auditó el código + artefactos + corpus. Norte (pedido del usuario): el router debe
> ofrecer SOLO las tools necesarias — no meter ruido. Recall ya está ~99.6%; el gap real
> es PRECISIÓN (subset promedia 4.7 tools/turno; debería ser ~1-2).

Confirmed — `whatsapp` is a real expected tool in 15 corpus rows, so the PT "abre o WhatsApp" miss is a genuine off-corpus generalization leak (the encoder didn't generalize the PT phrasing to the whatsapp tool). The git log returned nothing (corpus likely committed under a path move), but the artifact contents are confirmed live.

I now have all the ground truth I need. The headline reframe: **the held-out corpus is saturated (0.996/1.000 live), the stale docs claim 0.881/0.628 — the program's frontier has moved from "fix the corpus split" to "fix off-corpus generalization, multilingual breadth, MCP-prefer, and the 4B's actual tool choice."** Writing the master plan.

---

# MASTER PLAN — Router del gemma4_agent hacia su estado máximo

> **Hallazgo que reordena todo el programa (medido esta sesión, no del informe):** el holdout curado YA está saturado. Corrida en vivo (`scripts/router_eval.py --split both`, 2026-05-29):
> - **holdout: TOOL RECALL 277/278 = 0.9964 · NO-TOOL keep 86/86 = 1.0000**
> - **dev: 984/990 = 0.9939 · 378/379 = 0.9974**
>
> Los números de los informes (0.835/0.51 baseline, 0.881/0.628 post-rebuild) están **obsoletos**: el corpus creció a 1733 filas (era ~el mismo tamaño pero re-etiquetado y re-curado) y el router se re-saturó contra su propia distribución. **No es un pase degenerado:** las queries no-tool devuelven exactamente `{safety, session}` 86/86 veces, y las queries con tool promedian 4.58 herramientas (máx 6). El router abstiene de verdad.
>
> **Conclusión dura:** la frontera del programa ya NO es "subir recall en este split". Es **generalización fuera-de-corpus** (multilingüe real, MCP-prefer, fraseos no anticipados) y **que el 4B realmente ELIJA la tool correcta del subset**. El plan se reordena alrededor de esto.

---

## 1. Estado actual del router (verdad terreno)

### 1.1 El pipeline (lo que ES hoy)
Router unificado de 21 etapas en `gemma4_agent/routing/planner.py::select_tool_names` (líneas 157–727), orquestando 5 sub-módulos en `gemma4_agent/routing/`:

| Sub-módulo | Rol | Cita |
|---|---|---|
| `planner.py` | Orquestador + capa de keywords (170+ regex ES/EN) + gates de abstención + cap | `select_tool_names` 157–727; `_suggest_tools` 757–1290; `_cap_tools` 1404–1422 |
| `semantic_router.py` | Encoder FT (MiniLM) + centroides Tool2Vec (α=0.6) + cosine top-k (min_score 0.25) | `semantic_router.py:23-36, 183-188, 314-347, 360-391` |
| `exemplar_router.py` | Match exacto + voto sobre top-5 vecinos (umbral 0.92, conservador) | `exemplar_router.py:52-103` |
| `intent_router.py` | 5 centroides (info/action/chitchat/selfref/meta); gates `want_knowledge`, `is_conversational` | `intent_router.py:307-329` |
| `reranker.py` | Cross-encoder condicional, sólo en banda "vacío-pero-no-smalltalk" (p_no_tool < 0.85) | `reranker.py:81-98` |

Flujo (resumido): **normalización → exemplar → plan-mission → keywords → continuación-streaming → semántico (siempre) → intent+abstain head → gate conversacional → decisión de abstención + escapes → per-tool head → boost goal-mission → unión semántica+head → rescate cross-encoder → fallback base → filtros post-heurística → expansión related-tools (budget 3) → cap a 5 → inyección pending-intent post-cap → session siempre alcanzable.**

### 1.2 Artefactos entrenados (verificados en disco esta sesión)
- **Encoder FT** (`router_encoder_meta.json`): base `paraphrase-multilingual-MiniLM-L12-v2`, 3 epochs, batch 64, **4624 pares** de entrenamiento (sintéticos Tool2Vec + dev real; holdout excluido por hash estable). 384-dim, ~466 MB, NO commiteado (regenerable).
- **Abstain head** (`abstain_head.json`): regresión logística, **12 features**, bias 1.5837, **threshold 0.66**, `recall_floor 0.95`, CV interno dev: `notool_keep_added 0.604`, `tool_false_abstain 0.048`. Pesos en JSON (no pickle).
- **Tool2Vec** (`tool2vec_queries.jsonl`): **3573 queries** sintéticas multilingües (ES/EN/PT/FR/DE/IT).
- **Per-tool head** (`tool_head.json`): **62 tools** con peso/bias/threshold propio; encoder `router_encoder_ft`; top-3 firings, margen 0.05.
- **Exemplar index**: NPZ curado congelado (sin acumulación online).

### 1.3 Corpus de evaluación (verificado)
`router_eval_corpus.curated.jsonl`: **1733 filas**, schema `{q, expected, source, label_origin}`.
- **No-tool: 465 filas (26.8%)**; mediana **5 palabras**; **431 filas multi-tool** (≥2 expected).
- Fuentes: `tests_540.md` (500), `carter:*` (929), `traces.jsonl` (301).
- **Split:** SHA256(`router-eval-2026-05-20`+q) % 5 == 0 → holdout (20%). Dev=1369, holdout=364.
- Canaries: **66 filas** (`router_canaries.jsonl`).

### 1.4 Precisión medida HOY (en vivo, esta sesión — fuente de verdad)
```
[dev]      TOOL RECALL 984/990 = 0.9939   NO-TOOL keep 378/379 = 0.9974
[holdout]  TOOL RECALL 277/278 = 0.9964   NO-TOOL keep  86/86  = 1.0000
mean_subset (holdout)   = 4.58 tools (máx 6);  no-tool → {safety,session} 86/86
```
**Slices holdout:** short 106/106=1.000, continuation 35/35=1.000, multilingual 4/4=1.000 — **pero los conteos delatan el problema: 274 de 278 filas tool del holdout son `lang:es`; sólo 1 fr, 1 it, 2 pt, 4 "multilingual".** La saturación es contra una distribución casi-monolingüe.

---

## 2. El norte: qué es un router "perfecto" aquí

Un router "perfecto" para este sistema (4B local, el catálogo actual de tools compuestas, voz, CPU, multi-usuario/multi-idioma) **no es "100% en el holdout curado"** — eso ya está casi logrado y es engañoso. El máximo real se define sobre **cinco ejes simultáneos**, con gates duros:

| Eje | Métrica | "Hoy" (medido) | Máximo objetivo | Por qué ese número |
|---|---|---|---|---|
| **A. Tool recall (in-distribution)** | recall@subset, holdout | **0.9964** | mantener ≥ 0.97 | Techo honesto ~0.92–0.96 (ambigüedad de etiqueta + ruido STT); ya por encima → **defender, no mejorar** |
| **B. NO-TOOL keep** | abstención correcta | **1.0000** (holdout) | mantener ≥ 0.95 | Techo real 0.78–0.85 limitado por sesgo tool-call del 4B; el router ya hace su parte → **el cuello está en el 4B, no en el router** |
| **C. Recall fuera-de-corpus / multilingüe** | recall en held-out **de idioma** (pt/it/fr/de/ru/ja generados por LLM distinto) | **DESCONOCIDO** (probes: PT WhatsApp **falla**, "next train"→sin web **falla**) | ≥ 0.90, y **dentro de 0.05 del español** | Es **la frontera real**. Corpus 99% ES; universalidad es ley de producto (CLAUDE.md) |
| **D. End-to-end: el 4B ELIGE bien** | router×Gemma success (tool correcta llamada, no narrada) | **NO MEDIDO sistemáticamente** | ≥ 0.88 user-visible | `router 0.92 × Gemma ~0.92 ≈ 0.85`; el research lo marca como cuello compuesto. **El MCP-prefer vive aquí.** |
| **E. Latencia** | p95 CPU del router | ~30–50 ms (cascada actual) | ≤ 50 ms p95, ≤ 20 ms p50 | Presupuesto de voz tier-Alexa (4–5 s total); router debe vivir en decenas de ms |

**Definición operativa de "máximo":** A≥0.97 ∧ B≥0.95 ∧ **C≥0.90 con paridad de idioma ≤0.05** ∧ **D≥0.88 e2e** ∧ E≤50 ms p95, **sin que ningún subgrupo de idioma/dominio se degrade** (anti-regresión por slice, mandamiento #7 de CLAUDE.md).

El verdadero trabajo restante es **C y D**. A y B son problemas resueltos *en este corpus* y el riesgo es **regresarlos** al perseguir C/D.

---

## 3. Lo que el research ya estableció (NO re-litigar)

Decisiones cerradas por las 9 investigaciones — construir SOBRE esto:

**Arquitectura aceptada:**
- **Bi-encoder multilingüe como motor** (MiniLM FT actual / e5-small como upgrade). Multilingüismo por embeddings, **no** detector de idioma + traducción.
- **Tool2Vec** (tool = media de N query-embeddings sintéticas, no descripción terse). Ya shippeado (α=0.6, 3573 queries).
- **Abstain head calibrado** como palanca de NO-TOOL (logística, dev-only, threshold por CV). Ya shippeado.
- **Per-tool logit heads** (cada tool cruza su propia barra → anti-bloat). Ya shippeado (62 tools).
- **Cross-encoder SÓLO offline/condicional**, nunca en hot-path por turno (350 ms/batch revienta presupuesto).
- **Estado de sesión como input del router** (no como rescate post-hoc en agent.py) — para continuaciones/deícticos.
- **NO-TOOL como clase positiva entrenada**, no "baja confianza en todo".
- **Splitter multi-intent en Python pre-LLM** (el 4B no encadena: 0% medido).

**Rechazos firmes (NO revivir):**
- ❌ **router_v2 (BM25+RRF)**: fallo estructural, no de tuning. BM25 colapsa en queries de 5 palabras (TF→1), RRF amplifica ruido del ranker léxico degenerado. Atrapado en vivo (canary "de qué trata Dune"→backup_sync). **5 intentos fallidos** incl. tight-cluster band. **Eliminado del runtime; no es fallback.**
- ❌ **mDeBERTa-NLI / clasificador MoE sobre sintético**: drift al agregar tools, baja cache-hit. Muerto en Sprint 3a.
- ❌ **Regex multilingüe (ES+EN+PT+...)** como motor primario: falsos positivos, no escala.
- ❌ **Cross-encoder en hot path por turno**, **enviar-las-65-tools** (RAG-MCP: 13.62% baseline), **LLM-as-retriever** (latencia voz), **fine-tune del Gemma 4 principal** (rompe quant llama.cpp).
- ❌ **Cosine threshold absoluto cross-query** ("0.45 significa cosas distintas para 'mutea' vs 'qué tiempo hace'") — calibración debe ser relativa/por-clase.
- ❌ **Read/write operator head**: medido y rechazado — el LLM ya elige read/write vía el `action` enum del tool compuesto.

**Establecido sobre el 4B (toolcalling-nlu, crítico para el eje D):** el cuello de "no llama la tool" es **desalineación de entropía del primer token** (arranca en modo narrativo). Palancas baratas y ya probadas: **sampling greedy en action-mode** (+3–4/6), **prefill `<|tool_call|>`** (+2/6), **few-shot en formato nativo** (+1–2/6). **OJO:** la memoria del repo dice que **prefill `<|tool_call|>` fue MALA APUESTA** en vivo (thinking es load-bearing 4/6→0/6) — esto **contradice** al research y es un dato a respetar.

---

## 4. Los gaps reales entre "hoy" y "perfecto"

Ordenados por dónde realmente fuga precisión (no donde los docs viejos creían):

### GAP-1 — El corpus saturó: la evaluación dejó de discriminar (META-gap, el más grave)
0.996/1.000 holdout significa que **el harness ya no puede medir progreso ni regresión sutil**. Cualquier cambio "mejora" de 0.996 a 0.997 (1 fila) — ruido. **Sin una eval que discrimine, los 20 sprints son a ciegas.** Esto debe arreglarse PRIMERO o todo lo demás es no-falsable.

### GAP-2 — Generalización multilingüe real NO está medida y FUGA (eje C)
Corpus 99% ES (274/278 holdout). Probes off-corpus esta sesión:
- **PT "abre o WhatsApp" → `[app, window, browser, web, source_manager]`, SIN tool whatsapp** (que existe, 15 filas lo esperan). **Miss real.**
- **EN "what time is the next train" → `[media, browser, audio, system]`, SIN web/weather.** **Mis-route real.**
- Non-latin (ru/ja) ni siquiera se pueden *imprimir* (cp1252 crash en harness) — **ceguera de evaluación**, no se sabe qué hacen.
- FR/DE/IT media SÍ funcionan. La cobertura es parcial e impredecible.

### GAP-3 — MCP-prefer: el 4B prefiere tools familiares sobre MCP/específicas (eje D — el gap que pediste destacar)
El router promueve MCP con barra separada (`_MCP_PEAK_KEEP=0.30` vs 0.50 nativo, `planner.py:62, 317-331`), **pero el problema NO está en el router — está en el 4B**. Aunque el MCP entre al subset, el 4B **elige web/browser genérico** porque tiene más ejemplos en su prior. El research lo nombra (sesgo tool-call + dilución de atención) pero **el router no tiene mecanismo para sesgar la ELECCIÓN del 4B**, sólo la presencia. Cuellos concretos:
- El semantic encoder está entrenado SÓLO con descripciones de tools nativas; las MCP son externas/crudas → score MCP siempre marginal (~0.29). "Si una query MCP real cae en 0.31, gana por pelos" (weakness del audit planner).
- No hay separador principiado señal/ruido en el borde MCP↔nativo.
- El few-shot/prefill que sesgaría al 4B hacia la tool específica **no está instrumentado por-subset**.

### GAP-4 — Calibración fija, no adaptativa, sin held-out por idioma (eje C/B)
14 constantes hardcodeadas (`_SEM_CONFIDENT 0.45`, `_VETO_P 0.78`, `_MCP_PEAK_KEEP 0.30`, etc., `planner.py:41-93`). Calibradas en dev ES. `thresholds_by_lang` existe pero **vacío** (TODO per-idioma, audit artifacts). Cosine absoluto cross-query es exactamente lo que el research dice que falla.

### GAP-5 — Cap=5 es workaround de CUDA, no decisión de router (eje D/E)
`MAX_SELECTED_TOOLS=5` por bug #22527 (crash ~13k tokens a 8 tools). Pero la memoria del repo dice **flash-attn OFF eliminó #22527**. → El cap=5 puede ser una **restricción artificial ya innecesaria** que recorta segundas-opciones correctas (`_HEAD_TOP_N=3` mata la 2da tool en queries ambiguas).

### GAP-6 — Sin medición end-to-end router×Gemma (eje D)
El eval mide SÓLO routing (¿está la tool en el subset?), no si el 4B la **llama**. Toda la cadena C→D es invisible. El research insiste: "Recall@K ≠ task pass rate".

### GAP-7 — Artefactos estáticos / sin loop de auto-mejora
Tool2Vec, exemplar, abstain head: congelados. No hay re-centrado con queries reales, ni acumulación online de exemplars de alta confianza, ni log de "tool-out-of-subset" para reentrenar. El research lo especifica (review log, monthly refit) — no implementado.

### GAP-8 — Sobre-especificación frágil del veto (robustez)
El veto (stage 10, `planner.py:484-488`) exige 8 condiciones AND. Una falsa rompe el veto. Frágil ante fraseos nuevos. Mejor: head unificado que aprenda la decisión, no 8 gates encadenados.

---

## 5. El programa multi-sprint (el plan)

Secuenciado **de mayor palanca / menor riesgo → más difícil**. Cada sprint tiene gate medible, riesgo y dependencias. **Principio rector (lección router_v2):** no avanzar al sprint ambicioso si el barato ya alcanza el gate.

---

### SPRINT 0 — Recuperar capacidad de medir (desbloquea TODO)
**Objetivo:** una eval que vuelva a discriminar. Sin esto, GAP-1 hace ciegos los 20 sprints.
**Cambios:**
1. **Held-out de idioma generado por LLM distinto** (pt/it/fr/de + ru/ja/zh/ar), 100 frases × idioma, parafraseadas por 3er LLM, sin solापe coseno >0.95 con corpus. *Nunca* visto en train.
2. **Held-out adversarial** hand-curado: los misses off-corpus de hoy (PT WhatsApp, "next train") + fraseos raros + code-switch ES↔EN.
3. **Arreglar la ceguera cp1252** del harness (UTF-8 en prints/logs) — hoy non-latin ni se imprime.
4. **Reportar por-slice de idioma con n≥30 por idioma**, no n=1.
**Gate:** la nueva eval debe mostrar **<0.90 en al menos un slice de idioma** (si todo da 0.99, el set no discrimina → rehacer). Discriminación = éxito.
**Riesgo:** bajo (sólo evaluación, no toca runtime). Riesgo de mala generación sintética → mitigar con 3-LLM diversity + spot-check humano.
**Dependencias:** ninguna. **Es el prerrequisito de todos los demás.**

---

### SPRINT 1 — Medir end-to-end router×Gemma EN VIVO (eje D, regla #3.5)
**Objetivo:** saber el número real user-visible, no sólo routing.
**Cambios:** harness que corre el agente real (`scripts/_boot_server_for_eval.py` + `agent.run_content`), inyecta 80–120 comandos (incl. los off-corpus), y mide **¿el 4B LLAMÓ la tool correcta?** (no sólo si estaba en el subset). Separar: router-miss vs Gemma-miss (tool presente pero no llamada → MCP-prefer, narró en vez de actuar).
**Gate:** baseline e2e establecido con desglose router-miss/Gemma-miss/MCP-prefer. **Sin número, no hay sprint D.**
**Riesgo:** medio (corre el LLM real, no-determinista — correr 3-4 fraseos/intención por la regla del repo; el 4B rutea open vs search distinto).
**Dependencias:** Sprint 0 (set off-corpus).

---

### SPRINT 2 — Expansión de corpus multilingüe + dominio (eje C, alimenta train)
**Objetivo:** cerrar el sesgo 99%-ES.
**Cambios:** generar **30 queries × (catálogo actual de tools compuestas) × 6+ idiomas** con ruido de transcripción/registro (Tool2Vec/Re-Invoke), con filtro de consenso teacher (descartar donde LLM-teacher y cross-encoder-teacher discrepan). Versionar el corpus (git hash + config hash). Añadir los misses reales como filas etiquetadas.
**Gate:** corpus train multilingüe balanceado; el held-out de idioma (Sprint 0) sube su piso **sin regresar ES** (paridad ≤0.05 tras reentrenar en Sprint 3).
**Riesgo:** medio (quirks del generador → 3-LLM + spot-check; sobre-ajuste a tics sintéticos → diversidad en 3 ejes: idioma/registro/ruido).
**Dependencias:** Sprint 0.

---

### SPRINT 3 — Reentrenar encoder FT sobre corpus multilingüe (eje C, palanca decisiva)
**Objetivo:** mover el piso multilingüe del encoder.
**Cambios:** reentrenar el MiniLM FT (`MultipleNegativesRankingLoss` + hard-negatives de pares confundibles: audio/audio_device, whatsapp/app, web/browser) sobre el corpus de Sprint 2. **Holdout de idioma excluido por hash.** Evaluar e5-small como alternativa SÓLO si MiniLM no alcanza paridad (research lo deja como upgrade, no default — y la memoria dice que e5 colapsa cosines 0.82-0.96 en este task).
**Gate:** held-out de idioma recall ≥0.90 **y dentro de 0.05 de ES y 0.07 de EN**; **ningún slice ES/EN regresa >0.02**; holdout curado se mantiene ≥0.97. Latencia p95 ≤50 ms (mismo 384-dim → sin costo).
**Riesgo:** **alto de regresión** — reentrenar puede degradar el ES saturado. Mitigar: gate anti-regresión por slice + artefacto versionado por git-hash (reversible).
**Dependencias:** Sprint 2 (corpus), Sprint 0 (medición).

---

### SPRINT 4 — Calibración por idioma + abstain head v2 (ejes B/C)
**Objetivo:** que los thresholds dejen de ser ES-only.
**Cambios:** poblar `thresholds_by_lang`; reentrenar abstain head con features comparables cross-query (no cosine absoluto) + filas no-tool multilingües + adversariales (negación "no abras Steam", meta-directivas). Calibración por temperatura/isotónica; validar con Brier/ECE.
**Gate:** NO-TOOL keep ≥0.95 en held-out de idioma; `tool_false_abstain` ≤0.05 por idioma; ECE mejora vs v1. **Sin regresar el 1.000 ES.**
**Riesgo:** medio (recalibrar puede sobre-abstener → recall_floor 0.95 como guardia dura).
**Dependencias:** Sprint 3 (encoder nuevo cambia la geometría de features).

---

### SPRINT 5 — Resolver MCP-prefer y la ELECCIÓN del 4B (eje D — el sprint difícil que pediste)
**Objetivo:** que cuando una tool específica/MCP es correcta, el 4B la **llame**, no caiga a web/browser familiar.
**Cambios (en orden de riesgo):**
1. **Enriquecer descripciones MCP con example_queries** (Tool2Vec sobre MCP) → suben el score MCP de ~0.29 a banda competitiva, separador principiado señal/ruido.
2. **Subset ordering anti-primacy:** poner la tool específica/MCP de alta confianza PRIMERA en el subset (el research predice +5–15 pp por primacy en 4B).
3. **Few-shot turn-specific en formato nativo** sintetizado por el router cuando hay una tool específica de alta confianza (`call:mcp_tool{...}`) — enseña al 4B la *forma* de la invocación específica. **Cacheable.**
4. **Sampling greedy en action-mode** para reducir entropía del primer token (research: +3–4/6).
5. **NO usar prefill `<|tool_call|>`** salvo medición que contradiga la memoria del repo (mala apuesta: thinking load-bearing 4/6→0/6). **Medir, no asumir.**
**Gate:** en el set e2e (Sprint 1), MCP-prefer misses caen ≥50%; tool-call success ≥0.88 user-visible; **sin subir latencia >0** (few-shot cacheado).
**Riesgo:** **alto** — toca el comportamiento del 4B (no-determinista). Probar EN VIVO 3-4 fraseos/intención (regla #3.5). El prefill ya falló una vez.
**Dependencias:** Sprint 1 (medición e2e), Sprint 3 (encoder).

---

### SPRINT 6 — Revisar cap=5 y top-N de heads (ejes D/E)
**Objetivo:** quitar la restricción artificial si #22527 ya no aplica (flash-attn OFF).
**Cambios:** medir crash-threshold real con flash-attn OFF; si seguro, subir `MAX_SELECTED_TOOLS` a 6–8 y `_HEAD_TOP_N` a recuperar la 2da-opción correcta. Hacer `_SEM_TOPN` consistente con el cap (hoy son independientes → mismo query da subset distinto por path).
**Gate:** recall sube o se mantiene; **latencia del 4B p50 no empeora** (medir tokens de prefill); sin crashes en 50 corridas.
**Riesgo:** medio (regresar a OOM/crash). Gate de estabilidad duro + VRAMWatchdog.
**Dependencias:** Sprint 5 (e2e estable para medir efecto del cap).

---

### SPRINT 7 — Loop de auto-mejora (eje C/D, sostenibilidad)
**Objetivo:** que el router no vuelva a saturar/quedar estático.
**Cambios:** review-log de "tool-out-of-subset" (cuando el 4B llama algo fuera del subset → señal de miss del router); acumulación online de exemplars de alta confianza; re-centrado mensual de Tool2Vec desde queries reales; popularity-cap con decay 30-días (anti-Matthew effect). Invalidar cache semántica en señal negativa.
**Gate:** pipeline reproducible (todo regenerable desde scripts versionados); el review-log captura misses reales que la eval no anticipó.
**Riesgo:** bajo-medio (cuidado con poisoning del cache/exemplars → gate de confianza + spot-check).
**Dependencias:** Sprint 1 (instrumentación e2e da la señal).

---

### SPRINT 8 — Robustez estructural: simplificar el veto, deícticos/estado (robustez)
**Objetivo:** reemplazar gates frágiles por aprendizaje, integrar estado de sesión en el router.
**Cambios:** fusionar el veto de 8-AND en una decisión aprendida; mover continuación/deícticos (ring buffer + estado) a input del router (research: TripPy, no rescate en agent.py). Ring buffer Python para anáfora ("ciérralo", "ese") — no coref del 4B.
**Gate:** continuation recall ≥ pure-query+0.05; sin regresar in-distribution; menos superficie de regla (mandamiento "shrink not grow").
**Riesgo:** alto (refactor de control-flow; los deícticos ya los resuelve agent.py runtime — no romper eso).
**Dependencias:** Sprints 3–5 (encoder/calibración estables primero).

---

**Sprints 9+ (frontera, opt-in):** Model2Vec student (500× speedup si latencia aprieta tras crecer el corpus), code-switch slice, accent-holdout (Piper TTS + Whisper re-transcripción), FunctionGemma 270M como specialist para romper el techo NO-TOOL del 4B (fuera de scope del router pero es el techo honesto del eje B/D).

---

## 6. Cómo medimos el progreso

**Harness (extiende `scripts/router_eval.py`, no reemplazar):**
- **Split anti-overfit congelado:** SHA256(`router-eval-2026-05-20`+q)%5 — **mismo salt** en eval/train para no filtrar (ya consistente).
- **Reporte dual obligatorio:** `--isolated` (sin estado) vs `--inherit` (con continuación) — el estado no puede ocultar un base débil (constraint del operador).
- **Slices con n≥30:** por idioma (es/en/pt/fr/it/de/ru/ja), por longitud (≤4 palabras), por registro (continuación), por dominio.

**Tres held-outs independientes (Sprint 0), evaluados UNA vez por sprint, nunca inspeccionados para tunear:**
1. **Held-out de idioma** (LLM distinto) — mide eje C / universalidad.
2. **Held-out adversarial** (hand-curado: PT WhatsApp, "next train", negaciones, code-switch) — mide robustez.
3. **Canary set** (66 filas + crece) — ancla de bugs históricos reales (regla: "de qué trata Dune"→web, NO backup_sync).

**Gates por-dominio anti-regresión (mandamiento #7):** ningún slice de idioma/dominio puede caer >0.02 al mejorar el promedio. CI duro.

**Eval end-to-end (Sprint 1, la que importa para D):** corre el agente y el 4B REALES (regla #3.5), mide tool-call success user-visible, **desglosa router-miss vs Gemma-miss vs MCP-prefer**. 3-4 fraseos por intención (el 4B es no-determinista).

**Latencia:** p50/p95 del router en CPU por sprint (gate ≤50 ms p95); tokens de prefill del subset (gate: cap no infla el input del 4B).

**Definición de Hecho por sprint:** gate medido contra el criterio definido ANTES + held-outs sin regresión + fuentes citadas + memoria actualizada si hubo gotcha + prueba en vivo si tocó comportamiento del agente.

---

## Honestidad sobre lo difícil (separando hecho de hipótesis)

**Sé con evidencia (medido esta sesión):** holdout 0.9964/1.0000 real (no degenerado); corpus 99% ES; PT WhatsApp y "next train" fallan off-corpus; non-latin ni se imprime; cap=5; whatsapp es tool real con 15 filas.

**Hipótesis / falta confirmar:** (a) que reentrenar suba multilingüe sin regresar ES — **el riesgo central, no probado**; (b) que el MCP-prefer se arregle desde el router y no requiera tocar el 4B — el research sugiere que el techo (eje B/D) lo pone el 4B, no el router, y romperlo de verdad puede exigir FunctionGemma/modelo mayor (fuera de scope); (c) que prefill `<|tool_call|>` ayude — **la memoria del repo dice que falló**, contradice al research, hay que medir; (d) que cap>5 sea seguro con flash-attn OFF — plausible pero no re-medido.

**El gap honesto:** el router está casi-perfecto *en su corpus* y eso es precisamente la trampa. Los 20 sprints no son para subir 0.996→1.0 (ruido); son para que ese 0.996 sea verdad en **portugués, japonés, fraseos nuevos, y en la boca del 4B cuando elige la tool**. El Sprint 0 (recuperar medición) es no-negociable: sin él, todo lo demás es celebrar sin medir.

**Archivos clave:** `gemma4_agent/routing/planner.py` (orquestador, constantes 41-93, `select_tool_names` 157-727), `gemma4_agent/routing/semantic_router.py`, `gemma4_agent/routing/intent_router.py`, `gemma4_agent/routing/reranker.py`, `gemma4_agent/data/{abstain_head,tool_head,router_encoder_meta}.json`, `gemma4_agent/data/{tool2vec_queries,router_eval_corpus.curated,router_canaries}.jsonl`, `scripts/router_eval.py` (harness, split 51-60).