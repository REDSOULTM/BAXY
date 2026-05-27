# Tool-Routing para Gemma 4 local con 65 compound tools — Arquitectura Recomendada

**TL;DR**
- Para tu caso lo correcto es un **retriever híbrido (BM25 multilingüe + dense embeddings) sobre tool descriptions enriquecidas con queries sintéticas tipo Tool2Vec / Re-Invoke, fusionadas con Reciprocal Rank Fusion (RRF), un smalltalk-gate por centroide previo y SIN cross-encoder rerank en el path crítico**. El reranker se queda como herramienta offline para curar descriptions, no como producción.
- El embedding model concreto a usar es **`intfloat/multilingual-e5-small` quantized int8 ONNX (~113 MB, 117.65M params, 384 dim, 100 idiomas)** — no MiniLM-L12-v2, no bge-m3, no EmbeddingGemma. Cubre el requisito de multi-language sin language detector ni traducción interna, y entra holgado en el presupuesto de latencia.
- **Cross-encoder reranker (bge-reranker-v2-m3) NO va a producción**: 568M params, 2.27 GB en fp32 safetensors, latencia CPU medida ≈ 350 ms para un batch de 3 documentos (BSWEN, feb 2026). Para 16 candidatos serían varios segundos en CPU — repite el patrón del mDeBERTa-NLI que ya mataron.

---

## 1. Estado del arte aplicable a este caso

La literatura sobre tool routing se divide en tres olas; sólo una es relevante para vos:

- **Ola 1 — Fine-tuning del LLM principal**: Toolformer (Schick et al., 2023, arXiv:2302.04761), Gorilla (Patil et al., 2023, arXiv:2305.15334), ToolLLM/ToolLLaMA (Qin et al., 2023, arXiv:2307.16789), ToolGen (Wang et al., 2024, arXiv:2410.03439). **No aplica**: requiere fine-tunear el LLM con tu catálogo, lo cual rompe con Gemma 4 cuantizado en llama.cpp y no escala cuando agregás un tool nuevo. ToolGen además admite explícitamente un **sesgo de decoding hacia tools con más subtokens**: "tools with more unique tokens will have a higher probability to be retrieved" (arXiv:2410.03439).

- **Ola 2 — Hierarchical / agentic retrieval**: AnyTool (Du et al., ICML 2024, arXiv:2402.04253) usa GPT-4 como meta-retriever sobre 16k APIs de RapidAPI con tres niveles de agentes + self-reflection. **No aplica**: usa el LLM como retriever (lo que vos ya descartaste por latencia). Igual aporta un dato útil: el "plain agent" de GPT-4 sin retrieval logra sólo 14.0% pass rate en ToolBench filtrado, contra 58.2% de AnyTool — confirma que un retriever explícito vale, pero el costo agentic es prohibitivo para voz.

- **Ola 3 — RAG sobre tool descriptions (Tool RAG)**: la que aplica. Referencias clave:
  - **RAG-MCP** (Gan & Sun, May 2025, arXiv:2505.03275): demuestra empíricamente que retrieval simple sobre descripciones de tools sube tool-selection accuracy de **13.62% (Blank Conditioning, sin tools en contexto) a 43.13% (retrieval top-k)**, con reducción de tokens de **2133.84 → 1084 (49.2% menos)**. El baseline "Actual Match" (todos los tools correctos inyectados) sólo alcanza 18.20%, lo que muestra que **el problema NO es falta de tools en contexto sino dilución de atención**.
  - **Toolshed / Advanced RAG-Tool Fusion** (Lumer et al., ICAART 2025): pre-retrieval enrichment + intra-retrieval query decomposition + post-retrieval rerank. Reporta +46/56/47% absolute Recall@5 sobre ToolE single-tool, ToolE multi-tool y Seal-Tools. Tu mejor referencia directa.
  - **Tool2Vec** (Moon et al., 2024, arXiv:2409.02141, repo github.com/SqueezeAILab/Tool2Vec): en lugar de embedar la descripción, embedás varias example queries por tool y promediás. Reporta "up to 27.28 in Recall@K on ToolBench dataset and 30.5 in Recall@K on ToolBank". **Lo más cost-effective que podés implementar mañana.**
  - **Re-Invoke** (Chen et al., Google Research 2024): generación sintética de queries por tool + multi-intent ranking. Mejora consistente con backbones BM25 y dense.
  - **ToolRet benchmark** (Shi et al., March 2025, arXiv:2503.01763): muestra que embeddings genéricos fuertes en MTEB rinden mal en tool retrieval. Implica que **enriquecer descripciones importa más que cambiar el embedding model**.

Para tu setup (4B local, 65 tools, voz, multilingüe), **la única línea aplicable es Ola 3**, y dentro de ella la combinación Tool2Vec-style enrichment + hybrid retrieval + RRF (Toolshed minus el rerank pesado).

---

## 2. Técnicas a evaluar (8 candidatos)

### 2.1 Dense retrieval con embeddings multilingües instruction-aware
- **Cómo**: reemplazás `paraphrase-multilingual-MiniLM-L12-v2` por un embedding multilingüe más reciente. Tool descriptions enriquecidas con sinónimos y example queries en varios idiomas.
- **Latencia / tamaño**:
  - `multilingual-e5-small` — **117.65M params, 384 dim, ONNX int8 = 112.8 MB, fp32 = 448.58 MB** (huggingface.co/Teradata/multilingual-e5-small, Xenova/multilingual-e5-small). Sentence Transformers docs reportan **~3.08× speedup con ONNX int8 vs PyTorch fp32 en CPU** (sbert.net). Sin medición pública en ms para variant multilingual sobre CPU estándar; **estimación 15–40 ms** para queries <50 tokens en CPU moderno con int8.
  - `bge-m3` — 567M params, dense 1024 + sparse + ColBERT en un solo modelo, ~1.2 GB en Ollama. Más capaz pero ~5× más pesado.
  - `jina-embeddings-v3` — 570M params, 1024 dim con Matryoshka truncable a 32, LoRA por tarea. Comparable a bge-m3 en costo.
  - `EmbeddingGemma-300m` — **308M params, 768 dim Matryoshka a 128**, Q8_0 GGUF = 329 MB, F16 = 612 MB. CPU móvil (Samsung S25 Ultra, XNNPACK, 4 threads): **66 ms para 256 tokens** según litert-community/embeddinggemma-300m. El número "<15 ms" que circula es **EdgeTPU, no CPU** (developers.googleblog.com).
- **Pros**: cubre multi-language sin keywords. e5-small explícitamente trained sobre 100 idiomas.
- **Cons**: con descripciones terses falla — hay que enriquecer.
- **Ref**: huggingface.co/intfloat/multilingual-e5-small , huggingface.co/google/embeddinggemma-300m , huggingface.co/BAAI/bge-m3

### 2.2 Sparse retrieval (BM25 multilingüe sin hardcode)
- **Cómo**: BM25 sobre las descripciones tokenizadas con tokenizer Unicode genérico (no per-language stopwords). Librerías: `bm25s` (Lù 2024, arXiv:2407.03618), `rank-bm25`, `vectorchord-bm25`. Soportan UTF-8 y tokenización Unicode sin listas hardcoded.
- **Latencia**: sub-milisegundo para 65 tools.
- **Memoria**: trivial (<1 MB).
- **Pros**: cero ML, robusto a typos si combinás con stemming/character n-grams. Excelente para nombres propios ("Steam", "WhatsApp") que el embedding generaliza mal.
- **Cons**: solo falla cuando el usuario dice "dale play" y el tool dice "media controller — start/stop/pause".
- **Ref**: github.com/xhluca/bm25s

### 2.3 Hybrid retrieval con Reciprocal Rank Fusion
- **Cómo**: corrés BM25 y dense en paralelo, fusionás listas con RRF (Cormack, Clarke & Buettcher 2009): `score(d) = Σ 1/(k + rank_i(d))` con k=60. No requiere normalizar BM25 scores contra cosine.
- **Latencia**: max(BM25, dense) + fusión trivial. Para 65 tools, ≈ latencia del dense.
- **Pros**: en RAG-MCP y Toolshed hybrid > dense > sparse para tool retrieval. Resuelve casos canónicos como "send_email vs send_message" donde el dense puro confunde (~1 de cada 7 calls según el caso reportado en mejba.me/blog/mcp-is-dead-corsair-rag-tools).
- **Cons**: dos índices que mantener. Para 65 tools no importa.
- **Ref**: weaviate.io/blog/hybrid-search-explained , arXiv:2504.05324

### 2.4 Send-all-tools (sin pre-routing)
- **Cómo**: mandás los 65 schemas siempre.
- **Latencia**: 65 tools × ~120 tokens ≈ ~8k tokens de prefill. En Gemma 4 4B Q4 en CPU son segundos. **Rompe budget de voz.**
- **Cons**: RAG-MCP lo midió: accuracy cae a 13.62% (Blank Conditioning baseline) y "Actual Match" con tools correctos pre-inyectados llega sólo a 18.20% — la dilución de atención degrada igual aunque el tool correcto esté presente. **Descartado.**

### 2.5 Caching agresivo por similaridad semántica
- **Cómo**: el resultado del retrieval se guarda indexado por embedding de la query. Si una nueva query cae a similarity > θ de una cacheada, se reutiliza la lista.
- **Latencia**: cache hit ≈ <5 ms.
- **Pros**: el bench AWS/ElastiCache (Bhagdev, Nuthalapati, Song & Shah, AWS Database Blog 26-Nov-2025) sobre 63,796 queries de SemBenchmarkLmArena con cache.r7g.large + Titan Text Embeddings V2 + Claude 3 Haiku reportó **86% cost reduction y 88% latency improvement a threshold 0.75 manteniendo 91% answer accuracy**; individual cache hits redujeron latencia hasta **59× (6.51 s → 0.11 s)**. En tu caso (smalltalk + comandos repetitivos), un cache de ~500 entries con θ≈0.85 debería rendir 40–60% hit rate real.
- **Cons**: false positives si el threshold está mal calibrado.
- **Ref**: aws.amazon.com/blogs/database/lower-cost-and-latency-for-ai-using-amazon-elasticache-as-a-semantic-cache-with-amazon-bedrock/

### 2.6 Self-improving routing (online learning desde feedback)
- **Cómo**: pattern Toolshed/Millwright — cada vez que Gemma realmente llama un tool, agregás un triple `<query_embedding, tool, fitness>` a un review log. El retriever combina similarity con tool descriptions + similarity con historical reviews ponderada por fitness.
- **Latencia**: extra cosine sobre <1k entries → ~5 ms.
- **Pros**: aprende patrones coloquiales sin code change ("dale play" → media). Cierra el loop de feedback.
- **Cons**: necesita 1–2 semanas de tráfico para estabilizar.
- **Ref**: minor.gripe/posts/2026-03-13-millwright_smarter_tool_selection_with_adaptive_toolsheds

### 2.7 MoE-style classifier learned sobre data sintética
- **Cómo**: entrenás un clasificador multilabel (DeBERTa-base o XLM-R) sobre queries sintéticas generadas por LLM, predict subset directamente. Tool2Vec stage 2 (MLC) es esto.
- **Latencia**: ≈50–80 ms en CPU para 100M params.
- **Cons**: **es el mDeBERTa-NLI que ya mataste en otra forma**. Drift cuando agregás tool nuevo → re-entrenar. Si lo mataron por baja cache rate y memoria, este sufrirá lo mismo.
- **Recomendación**: **NO**.

### 2.8 Cross-encoder rerank sobre top-K
- **Cómo**: dense retrieval te da top-30; un cross-encoder (bge-reranker-v2-m3) re-puntúa cada par (query, tool_desc) y devuelve top-12.
- **Latencia / tamaño**: `bge-reranker-v2-m3` = **568M params, 2.27 GB safetensors fp32** (huggingface.co/BAAI/bge-reranker-v2-m3). CPU measurement (BSWEN, docs.bswen.com/blog/2026-02-25-best-reranker-models): **~350 ms para un batch de 3 documentos en CPU, ~80 ms en GPU**. Per-pair CPU ≈ 115 ms. Para 30 pares ≈ varios segundos en CPU. **Rompe budget de 300 ms.**
- **Recomendación**: **NO en hot path**. Útil como herramienta offline para curar tool descriptions o auto-generar example queries del log.

---

## 3. Recomendación final (arquitectura concreta)

### 3.1 Pipeline en 4 capas

```
turn → [Layer 0: smalltalk gate]
      → [Layer 1: semantic cache lookup]
      → [Layer 2: hybrid retrieval (BM25 + dense + RRF)]
      → [Layer 3: confidence-gated fallback]
```

**Layer 0 — Smalltalk gate (latencia <2 ms, sin embedding nuevo)**:
- Precomputás offline un "smalltalk centroid" (promedio de ~50 frases tipo "hola", "cómo va", "contame un chiste" en 5+ idiomas) y un "tools_global_centroid" (promedio de todas las tool descriptions enriquecidas).
- Si `cosine(query_emb, smalltalk_centroid) > 0.55` Y `cosine(query_emb, tools_centroid) < 0.35`, devolvés `[]`. Cubre el 46.6% de turnos a costo casi cero. **No es regex**, es geometría en el espacio embedding — multi-language sale gratis.

**Layer 1 — Semantic cache (latencia ~5 ms)**:
- Tras embedar la query (Layer 2 igual la necesita), buscás en cache LRU de hasta 1000 entries con TTL 24h. Si `cosine > 0.88` con una entry reciente, devolvés esa lista de tools.
- En tu caso de comandos domésticos repetitivos esperá 40–60% hit rate real (AWS midió >90% a θ=0.75 con 91% accuracy preservada).

**Layer 2 — Hybrid retrieval (latencia ~30–60 ms)**:
- **BM25** sobre tool descriptions con `bm25s` + tokenizer Unicode (sin per-language stopwords). 65 docs → sub-ms.
- **Dense** con `intfloat/multilingual-e5-small` int8 ONNX (~113 MB, 384 dim, 100 idiomas). Embedding de query estimado 15–40 ms en CPU; cosine contra los 65 tool embeddings pre-computados → sub-ms.
- **RRF** con k=60: combinás los dos ranks → top-16.
- Prepend `"query: "` a las queries y `"passage: "` a los docs (convención E5).

**Layer 3 — Fallback / confidence gating**:
- Si el top-1 score normalizado del híbrido < 0.30, mandás los 16 tools de mayor "popularidad global" (priors empíricos del log: filesystem, media, system, web, office) + el top-1 retrieved. El LLM principal todavía decide.
- Esto cumple el requirement G (graceful degradation): el router es advisory, Gemma 4 puede invocar cualquier tool aunque no esté en el subset.

### 3.2 Modelo de embedding recomendado: `intfloat/multilingual-e5-small` ONNX int8

| Atributo | Valor | Fuente |
|---|---|---|
| Parámetros | 117.65M | huggingface.co/Teradata/multilingual-e5-small |
| Dim | 384 | huggingface.co/intfloat/multilingual-e5-small |
| Tamaño disco ONNX int8 | 112.8 MB | Xenova/multilingual-e5-small/onnx |
| Tamaño disco ONNX fp32 | 448.58 MB | idem |
| Idiomas | 100 | model card |
| Latencia CPU (<50 tokens, int8) | 15–40 ms (estimación) | inferido de sbert.net "3.08× speedup with int8" + AIMultiple cluster sub-30 ms |

**Por qué no los otros**:
- **EmbeddingGemma-300m**: 2.6× los params de e5-small, 329 MB Q8 vs 113 MB int8. Su ventaja en MMTEB no se materializa con sólo 65 tools cortos. Útil si tu catálogo crece a >1000.
- **bge-m3**: 5× los params (567M), 1.1 GB fp16. Su ventaja (dense+sparse+ColBERT unificado) no compensa el costo, dado que ya tenés BM25 separado en Layer 2.
- **jina-embeddings-v3**: similar overhead. LoRA per-task añade complejidad sin payoff para 65 tools.

### 3.3 Formato de tool description recomendado

Cada tool tiene tres campos indexables, no uno:

```yaml
tool: office_suite
purpose: "Crear, editar y exportar documentos ofimáticos (Word, Excel, PowerPoint, PDF).
          Create, edit and export office documents."
example_queries:
  - "armame un PowerPoint sobre marketing digital"
  - "make me a slide deck about Q3 sales"
  - "preciso un Excel con los gastos del mes"
  - "crea un documento Word para mi tesis"
  - "exportá esto a PDF"
  - "podés generar un informe en hoja de cálculo"
related_to: ["filesystem", "vision", "web"]
```

- **Index dense**: embedés `purpose ⊕ example_queries` concatenado. 4–6 queries en al menos ES + EN (PT/IT/FR si el user base lo justifica). Esto es Tool2Vec aplicado minimalista (Moon et al. 2024, arXiv:2409.02141, reportado +30.5 Recall@K sobre ToolBank y +27.28 sobre ToolBench vs description-only).
- **Index BM25**: indexás `purpose + example_queries` igual.
- **Tamaño**: ~50–80 tokens por tool. Mandás top-16 → ~1.2k tokens de schemas en el system prompt. Token burn controlado.

**Por qué multilingüe explícito en vez de language-detect + translate**: el embedding ya cubre 100 idiomas. Mantener queries de ejemplo en el idioma real del usuario es más robusto que una traducción automática que introduce drift semántico. "dale play" no traduce literal a "give it play", pero el embedding lo entiende si tenés ejemplos similares.

### 3.4 ¿Cross-encoder rerank? **NO**

Hechos: `bge-reranker-v2-m3` = 568M params, 2.27 GB safetensors fp32. CPU medido ~350 ms por batch de 3 docs (BSWEN feb 2026). Para top-16 → varios segundos. Vos ya mataste un 280 MB mDeBERTa por cache hit rate 3.2%; meter 2.27 GB con peor latencia repite el error. **Uso alternativo**: corré el reranker offline sobre tu log de queries grabadas para auto-generar `example_queries` (pattern tipo DRAFT/Play2Prompt). Coste runtime cero.

### 3.5 Fallback / safety net

Tres mecanismos en cascada:
1. **Confidence threshold**: top-1 normalizado < 0.30 → fallback de tools populares.
2. **Recovery via main LLM**: si Gemma llama un tool fuera del subset, lo loggeás y lo agregás al review log con fitness positiva — el cache aprende solo.
3. **Self-improving loop**: cada tool-out-of-subset es negative signal para Layer 2. Compactación batch mensual: re-promediás example_queries con queries reales del log.

### 3.6 Multi-language

**No hagas nada especial**. El embedding multilingual-e5-small fue entrenado contrastive sobre 100+ idiomas. **No metés language detector. No metés traducción.** Sí: mantenés `example_queries` en al menos 2 idiomas por tool porque el embedding capta mejor el cluster cuando hay anclajes en cada idioma.

---

## 4. Pitfalls conocidos

1. **Drift cuando agregás tools nuevos**: tool A nuevo y tool B existente pueden caer al mismo cluster. Mitigación: cada vez que agregás un tool, corré la blind-test sobre queries históricas y revisá si el ranking del tool existente cae. **ToolRet** (arXiv:2503.01763) muestra que retrievers fuertes en MTEB caen significativamente en tool retrieval — no asumas transfer.

2. **Bias hacia descriptions largas / primacy bias**: documentado en PosIR (arXiv:2601.08363) y "Quantifying Positional Biases in Text Embedding Models" (arXiv:2412.15241). Los embedding models tienen primacy bias: la inserción/remoción de texto al inicio del documento reduce cosine similarity hasta 12.3% más que al final. Mitigación: **normalizá longitud** de tool descriptions a ~50–80 tokens con mismo número de example_queries (4–6). No dejes que `media_controller` tenga 200 tokens y `system` tenga 12.

3. **Ambigüedad entre tools similares (filesystem vs office, web vs browser)**: el problema canónico. Mitigaciones:
   - Campo `related_to:` para tie-breaking → si dos tools relacionados rankean top-2, incluí ambos.
   - En `example_queries` poné explícitamente queries que distingan: `filesystem` → "movés el archivo X a Y"; `office` → "crea el documento".
   - El caso `send_email` vs `send_message` (mejba.me/blog/mcp-is-dead-corsair-rag-tools) reportó confusión ~1 de cada 7 calls con naming parecido. Si tu vocabulario tiene colisiones, renombrá antes que retrievar.

4. **Token burn en system prompt**: con 16 tools × ~120 tokens estás en ~2k tokens de schemas. Mitigación: aplicá **EasyTool** (Yuan et al., arXiv:2401.06201, NAACL 2025) **offline**: comprimí tool docs a instrucciones concisas estandarizadas, reportado reducción significativa de token consumption preservando o mejorando performance.

5. **Cache poisoning**: si Layer 1 cacheó un mal subset y la query vuelve a hitear, repetís el error. Mitigación: invalidar entry cuando el LLM principal llama un tool fuera del subset.

6. **Embedding cold cache en cold start**: el modelo ONNX tarda 100–500 ms en cargar la primera vez. Warmup en boot con una query dummy.

7. **Matthew effect en popularidad**: tools que se llaman mucho aparecen siempre en el fallback → se llaman más. Mitigación: cap de popularidad con decay temporal (30 días) en el fallback.

8. **Recall@k no es task pass rate**: ToolRet (arXiv:2503.01763) muestra que correlacionan imperfectamente. Medí end-to-end: "Gemma terminó la tarea" no "el tool correcto estaba en top-16".

---

## 5. Si tengo que apostar (mayo 2026)

### Recomendación principal
**`multilingual-e5-small` int8 ONNX + `bm25s` con tokenizer Unicode + RRF (k=60) + tool descriptions enriquecidas Tool2Vec-style con 4–6 example_queries por tool en ES+EN + smalltalk-gate por centroide + semantic cache LRU 500 entries con θ=0.88.** Sin cross-encoder en hot path. Self-improving loop tipo Toolshed/Millwright como Sprint 2.

Esto es lo que harían los equipos serios hoy para 4B local + 65 tools + voz. Evidencia convergente:
- RAG-MCP (arXiv:2505.03275): 3.2× accuracy con retrieval simple, 49.2% menos tokens
- Toolshed (ICAART 2025): +46/56/47% Recall@5 con enrichment + hybrid
- Tool2Vec (arXiv:2409.02141): +30.5 Recall@K ToolBank con example queries
- Re-Invoke (Google Research 2024): ganancias consistentes con BM25 y dense backbones

Latencia esperada total: **gate (2 ms) + cache lookup (5 ms) + embed (15–40 ms) + BM25 (1 ms) + cosine 65×384 (<1 ms) + RRF (<1 ms) ≈ 25–50 ms** en CPU moderno. Holgado bajo 300 ms.

### Alternativa si la principal no alcanza
Si el blind-test sigue fallando >10% en queries con jerga regional muy específica después de implementar lo anterior — donde example_queries no alcance — la siguiente apuesta es:

**Upgrade del embedding a `EmbeddingGemma-300m` Q8_0 GGUF (329 MB) corrido en el mismo `llama.cpp` que Gemma 4**. No agregás runtime nuevo: reusás la infra de inferencia. State-of-the-art bajo 500M en MMTEB. Razón de no recomendarlo como primera opción: 2.6× los params de e5-small con ganancia marginal en un catálogo de sólo 65 tools cortos.

**Lo que NO haría**: ToolGen (fine-tune del LLM principal), AnyTool (LLM como retriever), classifier entrenado (mismo destino que el mDeBERTa), bge-m3 o jina-v3 (1+ GB para 65 tools cortos es over-engineering).

### ¿Es un open problem?
**No para este tamaño de catálogo.** Para 65 tools la receta dense+sparse+RRF+example_queries está bien establecida — Toolshed, RAG-MCP, Tool2Vec y Re-Invoke convergen. Donde sí hay open problems: **tool retrieval a >1000 tools**, **multi-step planning con dependencias entre tools**, y **robustez adversarial** (ToolTweak, arXiv:2510.02554). Ninguno aplica a 65 tools en single-turn voice.

---

**Implementación mañana**:
1. Bajar `intfloat/multilingual-e5-small` ONNX int8 de `Xenova/multilingual-e5-small`.
2. Instalar `bm25s`.
3. Reescribir las 65 tool descriptions como yaml con `purpose + 4–6 example_queries` en ES+EN.
4. Precomputar y persistir 65 embeddings (offline, 1 script).
5. Implementar las 4 layers en Python; target latencia <60 ms.
6. Re-correr el blind test. Apuntar a >70% en hard cases.
7. Sprint 2: agregar semantic cache + review log.

Si esto no llega al objetivo, el problema **no es el retriever** — es la calidad de las tool descriptions o del blind test. Mirá ahí antes de gastar otro sprint en infra.