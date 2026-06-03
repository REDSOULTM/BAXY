# Prompt para investigación: estrategia de routing universal sin regex

> Para Claude (claude.ai con Research mode o Opus 4.7 con web search
> habilitado). Pegar este bloque + las preguntas en una conversación
> nueva. La idea es que devuelva la mejor estrategia para nuestro
> caso específico, citando papers / repos / técnicas concretas.

---

## Bloque a pegar

```
Necesito que investigues la mejor estrategia de tool-selection para
un LLM agent local (Gemma 4, ~4B parámetros, llama.cpp, 100% local
sin cloud) que cumpla TRES requisitos no-negociables:

  1. Sin regex hardcodeados de keywords (la implementación actual
     usa 30+ buckets regex y falla con variantes triviales como
     "power point" vs "powerpoint" o cuando el usuario escribe en
     otro idioma).
  2. Multi-idioma universal. No queremos que el agente solo
     funcione en español o inglés; debe rutear correctamente
     cualquier idioma que el usuario use sin hardcodear listas
     de keywords por idioma.
  3. Latencia presupuesto: ≤300ms para la decisión de routing
     en cada turn (es voice-first, target end-to-end <4s).

CONTEXTO DEL SISTEMA ACTUAL:

- 65 "compound tools" expuestas al LLM (filesystem, audio, browser,
  steam, media, whatsapp, office, gui, web, vision, system,
  smart_home, etc). Cada tool tiene 4-21 actions distintas.
- Los nombres de tools y sus parámetros se envían al LLM en el
  system prompt como JSON schemas (formato OpenAI tool_calls). El
  total puede ir de 0 (smalltalk) a 16 tools en un turn (cap).
- En 712 turns medidos: 46.6% smalltalk (0 schemas), 50% regex match
  (puede ser parcial o equivocado), 3.4% semantic fallback.
- El semantic fallback actual usa sentence-transformers
  paraphrase-multilingual-MiniLM-L12-v2 (384 dim) sobre descripciones
  cortas de cada tool ("create PowerPoint, Word, Excel documents").
  Cosine similarity, top-k=12, min_score=0.25.
- En test ciego, el semantic actual acierta 50% en casos difíciles
  (variantes, idiomas, frases coloquiales). Las descripciones de
  tools son demasiado terse.
- El LLM principal (Gemma 4) puede invocar cualquier tool aunque
  no esté en el subset — el router es advisory, no estricto. Pero
  si la tool NO está en el subset, sus reglas de uso (TOOL_RULES)
  no se inyectan, y la descripción de schema sí (pero menos saliente).
- Mediante embeddings cacheados: cada query nueva cuesta ~50-100ms
  para encode + cosine.
- Tenemos infra para correr un segundo modelo ML pequeño (matamos
  un mDeBERTa NLI de 280MB hace un sprint porque su cache hit rate
  era 3.2%; estamos cuidadosos con agregar ML pesado).

PRÁCTICAS QUE YA DESCARTAMOS Y POR QUÉ:

- LLM-as-classifier (pre-call al mismo LLM principal pidiendo "qué
  tools necesitas"): agrega 1-3 segundos de latencia por turn. No
  viable para voice-first.
- Zero-shot NLI (mDeBERTa-xnli): probado, 3.2% cache hit, alto costo
  de memoria. Killed.
- Regex multilingüe (ES+EN+PT+FR+IT): killed en Sprint 3a, no se
  ejercitaba en práctica y aumentaba false positives.
- Catálogo cerrado de "intents" tipo Dialogflow/Rasa: hardcodea
  patrones, no escala con tools nuevas.

LO QUE BUSCAMOS:

Una arquitectura de tool-routing que:

  A) Genere subset de tools relevantes por turn (0-16 tools).
  B) Sin keyword regex (cero hardcode de palabras).
  C) Multi-idioma real (cualquier idioma que MiniLM o equivalente
     soporte).
  D) Latencia ≤300ms (excluyendo carga inicial de modelos).
  E) Funcione bien con frases coloquiales/regionales ("dale play",
     "podes apagar la wifi", "armame algo para mostrar").
  F) Sea robusto a typos y variantes ortográficas.
  G) Permita que el LLM principal vea las tools incluso cuando el
     router se equivoca (graceful degradation).

QUIERO QUE INVESTIGUES Y RESPONDAS:

1. **Estado del arte en tool-selection para agents locales.** Citá
   papers concretos (Toolformer, Gorilla, ReAct, ToolLLM, AnyTool,
   etc.) que aborden el problema de routing en agents con catálogos
   medianos (60+ tools). No me cuentes qué hace cada paper en
   detalle; dime cuál(es) son aplicables a NUESTRO caso (local,
   multi-idioma, latency tight).

2. **Técnicas concretas a evaluar.** Para cada una, dime:
   - Cómo funciona en 2-3 líneas.
   - Latencia esperada.
   - Costo de memoria/disk.
   - Pros para nuestro caso.
   - Contras para nuestro caso.
   - Si conocés implementación reference (repo, paper code).

   Candidatos que sé que existen pero no he evaluado:
   - **Dense retrieval con tool descriptions enriquecidas** (HyDE,
     ColBERT, embeddings instructional como E5-large-instruct,
     bge-m3, jina-embeddings-v3).
   - **Sparse retrieval** (BM25 sobre descripciones, sin hardcode).
   - **Hybrid retrieval** (dense + sparse fusionado vía Reciprocal
     Rank Fusion).
   - **Tool-augmented prompting** sin pre-routing (mandar las 65
     tools siempre en cada turn; medir si vale la pena el prefill
     extra).
   - **Caching agresivo de routing decisions** por similitud
     semántica al historial.
   - **Self-improving routing** que aprende del feedback de tools
     llamadas vs sugeridas (online learning ligero).
   - **MoE-style routing learned** (un pequeño classifier entrenado
     con datos sintéticos).
   - **Cross-encoder rerank** sobre top-K de bi-encoder.

3. **Recomendación final para nuestro caso.** Una arquitectura
   concreta, no genérica. Cita los componentes específicos
   (modelo X, técnica Y, parámetro Z) con justificación de por qué
   ESE y no otro. Incluí:
   - Modelo de embeddings recomendado (con tamaño en MB y latencia
     esperada en CPU/GPU si aplica). 
   - Formato sugerido de descripciones de tools (cuántas líneas,
     ejemplos, idiomas, etc).
   - Si vale la pena cross-encoder rerank o no.
   - Fallback / safety net cuando confidence es baja.
   - Cómo manejar multi-idioma (¿el embedding model lo cubre o
     hace falta detector de idioma + traducción interna?).

4. **Trampas conocidas en este tipo de sistema.** Cosas que la
   literatura warn sobre routing en agents y nosotros no
   anticipamos:
   - Drift cuando se agregan tools nuevas.
   - Bias hacia tools con descripciones más largas.
   - Ambigüedad entre tools similares (filesystem vs document, web
     vs browser).
   - Quema de tokens en el system prompt si las descripciones se
     enriquecen demasiado.

5. **Si tuvieras que apostar:** ¿qué hace un equipo serio HOY
   (2026) para tool-routing en un agent local de 4B con 65 tools
   y multi-idioma? Sin diplomacia. Dame UNA recomendación + UNA
   alternativa por si la primera no aplica.

REGLAS PARA TU RESPUESTA:

- Cita papers/repos/blogs con links si los tenés (Research mode).
- No inventes números de latencia. Si no sabés, decí "estimar".
- No me digas "depende" sin dar una decisión por default. Decidí
  vos asumiendo lo que ya te conté.
- Si la mejor solución es "esto es problema abierto", decímelo
  explícitamente — no inventes consenso que no existe.
- Mantenelo accionable. No necesito un survey académico, necesito
  saber qué implementar mañana.
- Tone: técnico, sin marketing, sin "agentic AI revolucionará".
- Output esperado: 1500-3000 palabras, secciones 1-5.
```

---

## Cómo usarlo

1. Abrí una conversación nueva en claude.ai con Research mode
   activado (si no, Opus 4.7 normal sirve igual).
2. Pegá el bloque entero.
3. Esperá ~5-10 min (Research mode hace búsquedas web).
4. Recibís un informe técnico con recomendación concreta.

Después de leer la respuesta, podemos:
- Implementar lo que recomienda (Sprint 8 de routing).
- Si recomienda algo que no estoy de acuerdo, debatimos.
- Si recomienda algo experimental que no es maduro, esperamos.

## Lo que NO le estoy preguntando (a propósito)

- "Cómo hacer un agent". Esto es solo routing.
- "Cuál es el mejor LLM". Gemma 4 está decidido.
- "Si vale la pena mover a la nube". No.
- "Cómo escalar". Es single-user local.

Eso enfoca la respuesta al problema real.

## Posible output esperado (basado en mi conocimiento de la literatura)

La respuesta más probable va a recomendar alguna combinación de:

1. **Modelo de embeddings instructional** (e.g. `bge-m3` o
   `jina-embeddings-v3`) en lugar de MiniLM. Razón: instruction-tuned
   embeddings entienden frases como instrucciones, no solo similitud
   léxica. Más caro (300-500MB vs 120MB) pero mejor accuracy.
2. **Descripciones de tools enriquecidas** con 3-5 ejemplos de uso
   por tool, en formato natural language (multi-idioma implícito
   porque el modelo es multilingual).
3. **Hybrid retrieval** (BM25 + dense) con Reciprocal Rank Fusion.
4. **Eliminar el regex inicial** — semantic primero, regex cero.
5. **Cross-encoder rerank** OPCIONAL si necesitamos más precisión.

Pero Claude va a verificar cuál es realmente el state-of-the-art
hoy. Si dice otra cosa, le hacemos caso.
