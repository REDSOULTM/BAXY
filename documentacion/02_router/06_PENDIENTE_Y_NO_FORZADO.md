# Lo pendiente y lo "no forzado"

> Este documento es la respuesta honesta a "qué falta y por qué NO se hizo".
> Cada ítem rechazado o diferido tiene la MEDICIÓN que lo justifica — no es
> intuición. Es lo que el próximo agente (o yo en otra sesión) debe leer antes
> de "arreglar" algo que ya se midió y se decidió dejar.

**Filosofía (CLAUDE.md):** no se fuerza un fix que pierde recall solo para tachar
un caso. "recall 0.022, FAIL" reportado honestamente vale más que esconderlo.
Distinguir hechos medidos de hipótesis.

---

## A. RECHAZADO con medición (NO volver a intentar igual)

### A1. Cluster-collapse de `{media, browser}`
- **Qué sería:** quitar `browser` cuando hay `media` con score mayor (parece
  ruido en "pon una canción").
- **Por qué NO:** **pierde 11 recall** en logs reales. "pon X en youtube" /
  "ponme billie jean en youtube" SÍ usan browser — YouTube/Netflix son web.
- **Lección:** media y browser **SOLAPAN dominio legítimamente**, NO es ruido.
- **Medición:** `[real] recall_perdido=11, ruido 0.922→0.801`.

### A2. Cluster-collapse de `computer_use`
- **Qué sería:** quitar computer_use cuando app/browser puntúan más alto.
- **Por qué NO:** pierde 1 recall — "andá a Instant Gaming y comprá Resident
  Evil" es goal-mission que necesita computer_use. 15 casos estrictos lo
  necesitan (Discord in-app, mic) y son frágiles.
- **Medición:** `[real] recall_perdido=1`.

### A3. Cluster-collapse de `source_manager`
- **Qué sería:** quitar source_manager cuando web puntúa más alto.
- **Por qué NO:** beneficio mínimo (ruido −0.026 curado) y pierde 1 recall
  ("de qué trata Dune"). Riesgo > beneficio.

### A4. Cluster-collapse de dominio genérico ({app,window} etc.) — `GEMMA4_CLUSTER_COLLAPSE`
- **Estado:** la infra existe pero **gated OFF** por default.
- **Por qué OFF:** medido que pierde recall (0.9964→0.9820); 5 casos esperan
  window/browser_real/uia específico. Ninguna regla estática los distingue.
- **Cuándo reactivar:** solo si el corpus de logs reales muestra que el collapse
  es seguro para un cluster concreto, con el gate de recall verde.

### A5. Auto-curar los labels del corpus de logs reales
- **Qué sería:** un clasificador (`classify_intent`) reescribe labels ruidosos.
- **Por qué NO:** un clasificador automático YA corrompió labels antes
  (`router_corpus_curate.py` lo advierte: "Opus es el oracle"). Probado: mi
  auto-clasificación movía comandos reales ("subelo a 40", "desmuteá") a
  NO-TOOL = PEOR que el label ruidoso.
- **Lección:** los misses de logs reales se atacan en el ROUTER, no maquillando
  el corpus.

### A6. Action anchors alemanes en `intent_router`
- **Qué sería:** agregar "mach lauter", "spiel ein lied" al centroide action.
- **Por qué NO:** REVERTIDO — IT/PT/FR ya estaban OK solo con las descripciones
  (S6); los anchors no movían la aguja (código muerto). El alemán seguía
  fallando.

### A7. Reentrenar el abstain head con datos multilingües (experimento aislado)
- **Qué sería:** agregar 178 pares tool2vec multilingües al training del head.
- **Por qué NO ayuda:** experimento medido — p_abstain de "mach lauter"
  0.72→0.70 (marginal); "spiel ein lied" hasta empeoró. El head opera sobre
  features de un encoder con cobertura DE débil; reentrenarlo no arregla
  features malas.

---

## B. DIFERIDO (vale la pena, pero requiere presupuesto)

### B1. ⭐ Encoder FT con datos alemanes (el fix REAL del multilingüe)
- **Qué resuelve:** el alemán coloquial corto ("mach lauter", "spiel ein lied")
  → hoy da subset vacío. También la precisión que NO se puede podar (distinguir
  "pon en youtube"→browser de "pon en spotify"→media).
- **Por qué es el único fix real:** la RAÍZ es el encoder base
  (paraphrase-multilingual-MiniLM) con cobertura débil del DE corto. "mach"
  (hacer) embebe en chitchat (chit 0.41 > act 0.35). Ninguna capa de arriba lo
  arregla (probado en A6, A7).
- **Costo:** ~12 h en GPU 4060 Ti, venv `.venv_router_train` (3.11 + CUDA).
- **Presupuesto a estimar antes de lanzar:** tiempo (~12h), VRAM, disco; qué
  pasa si falla a mitad. NO lanzar a ciegas (regla del proyecto).
- **Receta:** `scripts/train_router_encoder.py` → `scripts/router_ft_pipeline.py`
  (re-deriva Tool2Vec + abstain_head + tool_head con el encoder nuevo).
- **Datos a agregar primero:** más pares tool2vec en DE (y acentos diversos) para
  audio/media/system, generados con `router_tool2vec_generate.py`.
- **Anti-overfit obligatorio:** training solo sobre dev + sintéticos; una slice
  de universalidad (PT/IT held-out) valida que la ganancia no sea ES-only.
- **Gate de éxito a definir ANTES:** recall DE ≥ 0.80 sin bajar ES/EN, holdout
  curado ≥ 0.99, paridad por idioma ≤ 0.05.

### B2. Corpus multilingüe de eval
- **Qué falta:** el corpus curado es 99% ES (solo 4 filas multilingües: 1-2 por
  idioma fr/it/pt). No se puede MEDIR bien el multilingüe sin él.
- **Qué hacer:** construir un held-out diverso por idioma (no fine-tune sobre una
  voz/idioma — eso degrada a los demás, ley del producto).

### B3. Revisar cap = 5
- **Estado:** `MAX_SELECTED_TOOLS=5` fue workaround del crash CUDA #22527, que
  flash-attn-OFF ya eliminó.
- **Qué medir:** ¿subir el cap mejora recall sin degradar el tool-calling del 4B?
  PERO ojo: el norte del usuario es MENOS tools, no más. Subir el cap va en
  contra de la precisión. Medir el trade-off real con el 4B en vivo antes de
  tocar. Probablemente NO se toca.

### B4. Calibración del abstain head por idioma
- **Qué sería:** umbrales de abstención per-idioma (el DE necesita un umbral más
  permisivo que el ES).
- **Bloqueado por:** B1 (sin un encoder que separe el DE, el umbral no alcanza) y
  B2 (sin corpus DE no se calibra honestamente).

---

## C. Lo que NO se va a hacer (decisiones de diseño)

- **Listas de keywords por idioma para decidir qué hacer/contestar.** Frágil,
  monolingüe, rompe a hablantes de otros idiomas. Solo se permite: clasificación
  por embeddings multilingües + guardas estructurales (forma, no contenido).
- **Hardcodes / respuestas enlatadas.** El LLM responde. Lo único determinista:
  embeddings, guardas estructurales, estado del SO.
- **Reactivar el RouterV2 (BM25+RRF).** Borrado en el rebuild. El research de
  tight-cluster es de ESE sistema; no aplica.
- **Fine-tune sobre la voz/idioma del operador.** Mejora su recall pero degrada a
  todos los demás. Siempre evaluar contra held-out diverso.

---

## D. Estado de salud actual (lo que SÍ está bien)

Para no perder de vista lo logrado:
- Recall curado **0.9964** holdout, NO-TOOL keep **1.0000** — saturado.
- Recall real **89.1%** honesto (la verdad de campo).
- Ruido **−0.11/turno** esta sesión (1.62→1.51 holdout).
- Sin slice degradado (es 0.996, en/fr/it/pt 1.000).
- Robustez cubierta por invariantes en CI.
- 3 bugs reales arreglados (info-intent, exemplar abstain, browser_real ruido).

El router está en un estado considerablemente más preciso y robusto. El camino
restante hacia "100% perfecto" pasa principalmente por **B1 (encoder FT
multilingüe)** — el único fix que mueve lo que falta, y que requiere el
presupuesto de GPU que aún no se gastó.

---

## Resumen de prioridades para la próxima sesión

| Prioridad | Ítem | Bloqueante |
|-----------|------|------------|
| 1 | B2 — corpus multilingüe de eval | ninguno (es construcción de datos) |
| 2 | B1 — encoder FT con datos DE | presupuesto GPU 12h + B2 para medir |
| 3 | B4 — calibración abstain por idioma | B1 + B2 |
| — | B3 — revisar cap=5 | medir con 4B en vivo (probablemente no tocar) |

El orden importa: **sin B2 (corpus) no se puede medir B1/B4 honestamente.**
Construir el corpus multilingüe primero.
