# Arquitectura del router

> Cómo el router convierte el texto del usuario en un subset de tools.
> Punto de entrada de código: [`gemma4_agent/routing/router.py`](../../gemma4_agent/routing/router.py)
> → todo el pipeline vive en `select_tool_names()` de
> [`planner.py`](../../gemma4_agent/routing/planner.py).

---

## Principio rector

**UN pipeline, UNA decisión por turno.** Tras el rebuild de 2026-05-21 (que
aplicó 4 informes de research) se borró el viejo RouterV2 (BM25+RRF). Hoy hay
exactamente un router. Los módulos están separados por responsabilidad porque se
lee y se testea mejor así, pero la decisión es una sola.

Todo corre en **CPU**, decenas de ms en caliente (el chain de voz no usa GPU).

---

## El flujo por turno (orden real en `select_tool_names`)

```
texto del usuario
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 0. NORMALIZACIÓN                                                 │
│    _expand_abbreviations ("vol"→"volumen", "wsp"→"whatsapp")     │
│    _fold_text (minúsculas, sin tildes para el matching)          │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. EXEMPLAR ROUTER (exemplar_router.py)                          │
│    ¿El texto matchea EXACTO o casi-exacto (cos≥0.92) a un        │
│    ejemplo histórico ya etiquetado? → usa su label.              │
│    - match exacto → tools del ejemplo                            │
│    - voto ponderado entre vecinos near-tied                      │
│    - si el voto-ABSTENCIÓN gana por MARGEN → corta acá (NO-TOOL) │
│      [S3c: el margen evita que una pregunta-vecina envenene un   │
│       imperativo. Sin margen, "abre el navegador" daba vacío.]   │
└─────────────────────────────────────────────────────────────────┘
      │ (si no abstuvo)
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. PLAN + KEYWORD LAYER                                          │
│    plan_mission parte la frase en pasos (command_splitter)       │
│    _suggest_tools: regex multilingüe de verbos de acción         │
│    precisos (abrir, cerrar, subir volumen…). Alta precisión,     │
│    es el piso de recall para objetos OOV ("reproduce daddy       │
│    yankee" que el encoder no ubica).                             │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. RETRIEVAL SEMÁNTICO (semantic_router.py)  — corre SIEMPRE     │
│    encoder FT MiniLM + Tool2Vec (α=0.6) → suggest_tools_scored   │
│    Devuelve top-k tools con su score coseno.                     │
│    Promociones especiales:                                       │
│      - media-play fuerte → insertar `media` (multilingüe)        │
│      - mejor MCP ≥ _MCP_PEAK_KEEP → promover 1 al frente         │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. ABSTENCIÓN CALIBRADA (abstain_head.json)                      │
│    Regresión logística sobre features baratas (los 5 scores de   │
│    intención + forma del coseno + longitud + keyword_fired).     │
│    Decide P(no_tool). Si es charla/pregunta-sin-acción → vetar.  │
│    Escapes (protegen comandos reales que el head sobre-suprime): │
│      - confident-peak: 1 tool con score alto y gap claro         │
│      - _kw_protect: una keyword precisa disparó                  │
│      - wants_knowledge: pregunta del mundo → web/knowledge       │
│      - pending_intent / streaming-hint: continuación del turno   │
│         anterior                                                  │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. PER-TOOL HEAD (tool_head.json) — el anti-bloat                │
│    Cada tool tiene su PROPIO umbral calibrado. El subset son     │
│    solo las tools que individualmente cruzan su barra. "pausa" → │
│    {media}; "abre steam" → {steam,app}; "qué es pytest" → {}.    │
│    Chico y preciso POR CONSTRUCCIÓN.                             │
│    Rescates operacionales:                                       │
│      - computer_use si cu_score ≥ _CU_SEM_RESCUE (in-app nav)    │
│      - goal-mission ("ve a X y luego a Y") → computer_use        │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. PODA + CAP                                                    │
│    wants_knowledge → asegura web/knowledge alcanzables           │
│    _collapse_domain_clusters ({app,window}→app)  [gated OFF]     │
│    _collapse_hierarchical ({browser,browser_real}→browser)       │
│       [S3d: quita browser_real cuando es nav simple]             │
│    _cap_tools(MAX_SELECTED_TOOLS=5)                              │
│    + pending_intent al frente (sobrevive el cap)                 │
│    + session SIEMPRE alcanzable (append post-cap)                │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. REORDEN ANTI-PRIMACY (_antiprimacy_order)  [S5, b812841]      │
│    El cap ya decidió QUÉ tools entran; este reorden cambia solo  │
│    el ORDEN, no el CONJUNTO. La tool de DOMINIO de mayor score   │
│    va PRIMERA (los LLMs atienden más a lo primero — "Lost in the │
│    Middle", arXiv:2307.03172). pending_intent queda fija al      │
│    frente; las tools de infra (session/verify/state/dependency/  │
│    safety) quedan al final. Gate GEMMA4_ANTIPRIMACY=1 (default). │
│    [Estaba mergeado pero INERTE hasta b812841: schemas_for_names │
│     descartaba el orden con un set; fix = preservar orden de     │
│     `names` + cache keyed por tuple.]                            │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
   subset final ordenado (≤5 tools de dominio + meta) → al LLM (modelo Gemma 4 E2B-FT)
```

---

## Las "señales" y cómo se combinan

| Capa | Fuerza | Rol |
|------|--------|-----|
| **Keyword** | Alta precisión | Piso de recall; atrapa objetos OOV el encoder no ubica |
| **Exemplar** | Memoria | Casos históricos ya resueltos; corta temprano si abstención clara |
| **Semantic (encoder FT + Tool2Vec)** | Cobertura | Intención en cualquier idioma, sin mantenimiento de regex |
| **Abstain head** | Calibrado | UNA decisión NO-TOOL; mata el ruido en charla/preguntas |
| **Per-tool head** | Anti-bloat | Subset chico por construcción (cada tool su umbral) |
| **Reranker (cross-encoder)** | Rescate condicional | Solo en la banda "vacío-pero-no-charla"; el camino común no paga |
| **Anti-primacy (orden)** | Sesgo de elección | Reordena el subset (la tool top-score primero) para subir P(el 4B la elija). NO cambia el conjunto. [S5, gate `GEMMA4_ANTIPRIMACY`] |

**Regla de no-regresión:** la keyword y el exemplar GARANTIZAN que un comando
real nunca se silencie; el abstain head solo puede vetar lo que NINGUNA señal
fuerte protege.

---

## Los 5 centroides de intención (`intent_router.py`)

El clasificador de intención es 100% semántico (anchors multilingües, sin
keywords). Cinco clases, cada una un centroide promediado de sus anchors:

- **info** — pregunta sobre el mundo ("qué es X", "hablame de Y") → web/knowledge
- **action** — comando de PC ("abre Steam", "sube el volumen")
- **chitchat** — charla/relleno ("hola", "gracias", "jajaja")
- **selfref** — pregunta sobre el asistente ("quién eres", "qué podés hacer")
- **meta** — directiva de cómo responder ("no uses herramientas")

`wants_knowledge(text)` = info es el argmax y supera action por margen.
`is_conversational(text)` = chitchat∪selfref supera action∪info → abstener.

---

## Por qué cap = 5

`MAX_SELECTED_TOOLS = 5` (env `GEMMA4_MAX_SELECTED_TOOLS`). Originalmente fue un
workaround del crash CUDA #22527, pero flash-attn-OFF eliminó ese crash. Hoy se
mantiene como **disciplina de precisión**: más de 5 tools degrada el
tool-calling del 4B (riesgo R7 del research). Ver
[06_PENDIENTE_Y_NO_FORZADO.md](06_PENDIENTE_Y_NO_FORZADO.md) sobre revisarlo.

---

## Robustez: agregar tools/MCPs sin desconfigurar

El router decide por VARIAS capas. Una tool de dominio nueva debe enrolarse en
≥1 capa (descripción semántica, per-tool head, o tool2vec) o queda **invisible**.
[`test_router_coverage_invariant.py`](../../gemma4_agent/tests/test_router_coverage_invariant.py)
congela esa invariante: falla ruidoso con el nombre exacto de la tool huérfana.

Para MCPs, `semantic_router.enroll_mcp_tools()` los inscribe dinámicamente
(namespaced `mcp__server__tool`). El test verifica que enrolar 12 MCPs
irrelevantes NO le quita su tool nativa a ninguna query, NO se cuela, y
de-enrolar restaura el subset exacto. Ver
[03_GATES_Y_CONFIG.md](03_GATES_Y_CONFIG.md) (gate `GEMMA4_MCP`).
