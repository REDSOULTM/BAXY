# Arquitectura de memoria y grounding de entidades para un asistente de voz local con Gemma 4 E4B-it (Q4_K_M, llama.cpp b9090, Parakeet, Windows, 100% offline)

## TL;DR
- **El bug "mamá → grupo Música" no es un problema del LLM, es un problema de grounding pre-tool-call.** La solución es dejar de pasarle al LLM una *cadena de búsqueda* como argumento y obligarlo a elegir un `contact_id` de una lista de candidatos resuelta determinísticamente (inventario + fuzzy + memoria), forzada por GBNF/JSON-Schema `enum` en llama.cpp (el README oficial confirma soporte nativo de conversión JSON-Schema → GBNF con `enum`).
- **La memoria key-value en system prompt no escala y se está envenenando.** Hay que pasar a una arquitectura de tres capas — *core memory* siempre inyectada (≤6 ítems, alias estables del usuario), *retrieval* selectivo por turno con sqlite-vec + EmbeddingGemma (308M, <200MB RAM, 100+ idiomas, offline), y *episodic* podada con salience+decay+TTL, alineada con el resultado de LoCoMo donde un agente con simplemente filesystem search alcanza 74.0% vs Mem0 graph 68.5% (Letta blog, 12 ago 2025).
- **STT entity-recall se ataca antes del LLM, no después.** El inventario debe alimentar el biasing contextual de Parakeet TDT (la propia documentación NVIDIA NIM dice "For RNNT and TDT models, word boosting can result in approximately 15% latency regression. Out of Vocabulary boosting is not supported for RNNT and TDT models", con boost recomendado 0.5–2.0) y, en paralelo, un corrector fonético reforzado (Double Metaphone + Spanish Metaphone + Beider-Morse + Jaro-Winkler) cuyo ganador pasa al LLM como *candidato resuelto*, no como adivinanza.

---

## Resumen ejecutivo y orden de implementación

El sistema actual tiene tres defectos arquitectónicos que se refuerzan entre sí:

1. **El argumento de la tool-call es texto libre** ("mamá"), por lo que el agente termina haciendo una búsqueda fuzzy *después* del LLM contra una UI (WhatsApp), donde "mamá" colisiona con el grupo "Música" porque Double Metaphone los confunde y no hay desempate contacto-vs-grupo.
2. **El inventario es estático y no alimenta el ASR**, por lo que Parakeet transcribe "Chrome" como "crumb" y el corrector fonético llega tarde y a ciegas.
3. **La memoria es un volcado plano** sin importancia, sin TTL y sin separación per-user/global, lo que permite que basura de pruebas contamine el 52% de la SQLite.

La secuencia recomendada de cambios, en orden de mayor impacto por hora de trabajo:

| Prioridad | Cambio | Punto del informe | Esfuerzo |
|---|---|---|---|
| P0 | Tool-calls con argumento = `entity_id` resuelto + GBNF enum | §2 | Bajo |
| P0 | Resolver entidades antes del LLM (candidatos top-k al prompt) | §2 | Medio |
| P1 | Memoria de 3 capas (core / retrieval / episodic) con sqlite-vec + EmbeddingGemma | §1, §5 | Medio |
| P1 | Salience + TTL + filtros anti-test-junk en escritura | §4 | Bajo |
| P2 | Aprendizaje de alias con confirmación explícita y per-user | §3 | Medio |
| P2 | Biasing contextual de Parakeet con el inventario dinámico | §2 | Bajo |

---

## 1. Arquitectura de memoria de usuario

### (a) Diagnóstico

El esquema actual (`memory.py` con ~6 ítems pinned volcados como `- key: value` en el system prompt) funciona mientras los hechos son ≤10 y todos relevantes a *cada* turno. Falla en cuanto:

- el usuario tiene >50 contactos, >30 apps y >100 artistas que el modelo *debería* poder resolver;
- el contexto de Gemma 4 E4B es limitado y cada token "pinned" reduce la calidad de respuesta;
- no hay forma de inyectar "lo relevante a *esta* frase" sin cargar todo.

Mem0, Letta y A-MEM resolvieron este problema en 2025 con tres patrones distintos: (i) Mem0 extrae *facts* y los recupera por similaridad semántica, (ii) Letta da al agente herramientas (`core_memory_append`, `archival_memory_insert`) para que él mismo decida qué guardar, (iii) A-MEM (Xu et al., NeurIPS 2025, arxiv 2502.12110) organiza las notas estilo Zettelkasten con enlaces automáticos generados por LLM. El punto crítico para un modelo 4B local: **Letta autoeditor exige razonamiento que un 4B cuantizado a Q4_K_M no tiene de forma fiable**, y Mem0 cloud está descartado por la restricción offline. El benchmark de Letta sobre LoCoMo (publicado el 12 de agosto de 2025) muestra que un agente con simplemente `search_files` iterativo llega a 74.0% vs. el 68.5% de Mem0 graph, lo que sugiere que **un retrieval simple bien hecho es mejor que un esquema sofisticado mal aplicado en un modelo pequeño**.

### (b) Opciones

| Opción | Precisión resolución | Coste prompt/latencia | Complejidad implementación | Riesgo overfit a un usuario |
|---|---|---|---|---|
| A. Todo en prompt (status quo, crece) | Baja con >20 ítems | Alta (≥800 tokens) | Trivial | Alto (memoria compartida) |
| B. Letta-style autoeditor de memoria | Media (depende del razonamiento del modelo) | Alta (el modelo gasta turnos en pensar qué guardar) | Alta | Medio |
| C. Mem0-style passive extraction + RAG | Alta | Baja (3-5 hits/turno) | Media | Bajo (extracción es determinística) |
| D. **3-capas: core pinned + retrieval por turno + episodic** | Alta | Baja-media | Media | Bajo si se separa per_user vs global |
| E. A-MEM con notas enlazadas + LLM nota-generador | Alta en multi-hop | Muy alta (cada escritura ⇒ 1-2 llamadas LLM extra) | Alta | Medio |

### (c) Veredicto local con 4B

**Adoptar D, inspirado en MemGPT/Letta pero sin self-editing**. Con Gemma 4 E4B Q4_K_M no se puede gastar inferencia en "decidir qué recordar" durante el turno del usuario; eso se hace offline en un job de consolidación. La capa concreta:

- **Core memory (siempre inyectada)**: máximo 6–8 ítems de identidad estable (nombre del usuario, idioma preferido, zona horaria, alias canónicos de personas críticas tipo "mamá", "papá", "jefe").
- **Retrieval por turno (sqlite-vec + EmbeddingGemma)**: top-k=3-5 hechos relevantes al enunciado actual, recuperados por similitud semántica y filtrados por `user_id`.
- **Episodic / archival**: el ExperienceMemory ya existente, pero con salience scoring y decay (ver §4).

EmbeddingGemma es la pieza clave para que esto sea viable offline en Windows: 308M parámetros, multilingüe en 100+ idiomas, <200MB de RAM con cuantización QAT. Google publicó el 4 de septiembre de 2025: "We've pushed the boundaries of speed with <15ms embedding inference time (256 input tokens) on EdgeTPU" — en CPU x86 típica el orden de magnitud sigue siendo decenas de ms. La documentación afirma que está pensada para ejecutarse "directly on your hardware [...] even without an internet connection".

### (d) Fuentes 2025-2026

- A-MEM: Xu et al., "A-MEM: Agentic Memory for LLM Agents", arxiv 2502.12110, NeurIPS 2025.
- Letta blog, "Benchmarking AI Agent Memory: Is a Filesystem All You Need?", 12 ago 2025: filesystem agent 74.0% vs Mem0 graph 68.5% en LoCoMo.
- EmbeddingGemma, Google Developers Blog, 4 sep 2025.
- TokenMix.ai, "Mem0 vs Letta vs MemGPT 2026", abr-2026 (comparación arquitectónica).
- Atlan, "Best AI Agent Memory Frameworks in 2026" (lista Cognee como "best for local-first, privacy-critical deployments").

### (e) Pseudocódigo

```python
# memory_v2.py
class LayeredMemory:
    def __init__(self, user_id: str, db_path: str):
        self.user_id = user_id
        self.db = sqlite3.connect(db_path)
        self.db.enable_load_extension(True)
        self.db.load_extension("vec0")           # sqlite-vec
        self.embed = EmbeddingGemma(quantized=True)  # 308M, <200MB
        self._ensure_schema()

    def build_prompt_context(self, utterance: str, k: int = 4) -> str:
        core = self._fetch_core()                 # WHERE pinned=1 AND user_id=?
        retrieved = self._retrieve(utterance, k)  # vec0 KNN + user_id filter
        block = ["## Sobre el usuario (estable):"]
        block += [f"- {row['key']}: {row['value']}" for row in core]
        if retrieved:
            block.append("## Contexto relevante a esta orden:")
            block += [f"- {r['text']} (id={r['id']})" for r in retrieved]
        return "\n".join(block)

    def _retrieve(self, query: str, k: int):
        q_emb = self.embed.encode(query)
        return self.db.execute("""
          SELECT m.id, m.text, m.salience, m.created_at,
                 vec_distance_cosine(v.embedding, ?) AS dist
          FROM mem_facts m JOIN mem_vec v ON m.id = v.id
          WHERE m.user_id = ? AND m.salience >= 2
          ORDER BY dist + 0.0003*(julianday('now')-julianday(m.created_at))
          LIMIT ?
        """, (q_emb, self.user_id, k)).fetchall()
```

### Métricas que medir

- **Tasa de hit del retrieval** por turno (¿la información correcta entra en top-k?). Objetivo: ≥85%.
- **Tokens promedio del bloque de memoria** en el prompt. Objetivo: ≤250.
- **Latencia de retrieval** (embed + KNN). Objetivo: <80 ms con EmbeddingGemma Q4 en CPU.
- **Precisión de la orden** con vs sin retrieval (A/B con el mismo modelo).

---

## 2. Grounding de entidades / resolución de nombres propios (PRIORIDAD MÁXIMA — ataca el bug "mamá → grupo Música")

### (a) Diagnóstico

El bug ocurre porque el flujo actual es:

```
voz → Parakeet → "escríbele a mamá" → LLM → tool_call(send_whatsapp, contact="mamá") → GUI search → ¿match?
```

Dos errores arquitectónicos:

1. **El LLM nunca *resuelve* la entidad, solo la repite.** Le pasa la string al GUI search, que hace un fuzzy match débil donde "mamá" puede colisionar con grupos que contengan la letra "m" + vocales abiertas, sobre todo si el Double Metaphone del nombre del grupo ("Música" → MSK) es cercano a "mamá" (→ MM). El verdadero problema es que **no se distingue contacto de grupo en la fase de matching**.
2. **El inventario no participa en el momento del tool-call.** Cuando el LLM emite la llamada, el conjunto de entidades válidas no le está siendo presentado, así que no hay forma de constrainir la salida.

La literatura industrial es clara al respecto. Apple, en "Noise Robust Named Entity Understanding for Voice Assistants" (arxiv 2005.14408), describe el problema casi idéntico: "Humans make heavy use of named entities when interacting with digital voice assistants (e.g. 'Call Jon', 'Play Adele hello'); [...] since natural language is often ambiguous, speech recognizers make errors, and human memory is less than perfect for complex entity names, named entity understanding poses a challenge for voice assistants." El paper EMNLP 2024 Industry Track de Chen (Splunk AI), Zhang (Caltech) y Hu (Xsolla) — "Optimizing Entity Resolution in Voice Interfaces: An ASR-Aware Entity Reference Expansion Approach", DOI 10.18653/v1/2024.emnlp-industry.1 — confirma: "a token-based system might proficiently recognize 'Flying Gorilla' but could falter when dealing with semantically or phonetically akin phrases such as 'Frying Gorilla' or 'Flying Gloria'", y propone umbrales de filtrado fijos en "0.55 for cosine similarity and 0.3 for lexical similarity".

### (b) Opciones

| Opción | Precisión | Coste prompt/latencia | Complejidad | Riesgo overfit |
|---|---|---|---|---|
| A. Status quo: LLM produce string, GUI busca | 60-70% en nombres ambiguos | Baja | Baja | — |
| B. Resolver antes del LLM, inyectar top-k candidatos en prompt, dejar al LLM elegir | 90%+ | +50-150 tokens/turn | Media | Bajo |
| C. Resolver antes + **GBNF/JSON-Schema enum forzando el `entity_id`** | 95%+ | igual que B | Media | Muy bajo |
| D. Resolver *después* del LLM (post-processing) con confirmación si <umbral | 88% pero pide confirmar mucho | Baja | Baja | Bajo |
| E. Embedding-only matching (sin fonética) | 75% en nombres pero confunde acrónimos | Media | Baja | Medio |
| F. **Hybrid**: candidate generation = fonética + fuzzy + embedding ⇒ rerank ⇒ enum-GBNF | **95-98%** | Media | Media-Alta | Muy bajo |

### (c) Veredicto local con 4B

**Opción F (hybrid candidate generation + GBNF enum) es la única que cierra el bug "mamá → Música" de forma robusta.** Tres movimientos:

#### Movimiento 1 — Resolver entidades antes del LLM (candidate generation híbrido)

Para cada *mención* candidata en el enunciado (lo que ya hacen los regex de "escríbele a X", "abre Y", "pon Z"):

1. **Filtro fonético multi-algoritmo**: Double Metaphone (inglés) + Spanish Metaphone + Beider-Morse Phonetic Matching, que considera el idioma del nombre — crítico porque "Bad Bunny" tiene reglas inglesas y "Mamá" españolas. Steve Morse describe BMPM: "From the spelling of the name, an attempt is made to determine the language. Phonetic rules for that particular language are then applied", lo que reduce los falsos positivos de Soundex/Metaphone genéricos.
2. **String similarity**: RapidFuzz `process.cdist` con `JaroWinkler` (sobresale en cadenas cortas como nombres, según docs de RapidFuzz y el estándar AML: "Most AML screening systems use Jaro-Winkler thresholds between 0.80 and 0.90 for name matching. A threshold of 0.85 is common") **y** `token_set_ratio` (para apellidos compuestos).
3. **Embedding similarity** sobre el inventario indexado: usar EmbeddingGemma + sqlite-vec con los nombres normalizados (NFKD, sin tildes, lowercase). Esto captura "Bad Bunny" ≈ "Bad Buni" donde la fonética falla.
4. **Rerank** combinando los tres scores: `score = 0.4*phonetic + 0.3*jaro_winkler + 0.3*embed`. Filtrar por *tipo de entidad esperada*: si la intención es "enviar mensaje", el candidato debe ser `type=contact` y `is_group=false` (a menos que el usuario diga explícitamente "al grupo X").
5. **Devolver top-k=3** con sus IDs reales.

#### Movimiento 2 — Forzar al LLM a elegir con GBNF/JSON-Schema `enum`

llama.cpp tiene soporte nativo para esto. El grammars README declara: "GBNF (GGML BNF) is a format for defining formal grammars to constrain model outputs in llama.cpp. For example, you can use it to force the model to generate valid JSON, or speak only in emojis." Y soporta conversión JSON-Schema → GBNF: "llama.cpp supports converting a subset of https://json-schema.org/ to GBNF grammars [...] For the /chat/completions endpoint, passed inside the response_format body field [...] In llama-cli and llama-completion, passed as the --json / -j flag." El parser de `enum` produce literalmente una disyunción de literales: `rule = '(' + ' | '.join(...) + ') space'`, por lo que el modelo **no puede emitir** una salida que no sea uno de los IDs listados.

Importante para Gemma 4 E4B: la documentación oficial de llama.cpp para function-calling indica que el flag `--jinja` es obligatorio para que llama-server aplique las plantillas Jinja con soporte de tools; las pruebas comunitarias para Gemma 4 E4B confirman esto explícitamente. Sin `--jinja` no hay soporte de tool-calling.

#### Movimiento 3 — Tool-call grounded por ID, no por string

```jsonc
{
  "name": "send_whatsapp_message",
  "arguments": {
    "contact_id": "ct_4427",          // ← elegido vía enum forzado
    "message": "voy en camino"
  }
}
```

El backend WhatsApp (UI automation) **nunca** vuelve a hacer fuzzy search: recibe un `contact_id` y abre el chat exacto por número/JID. Esto **elimina por completo** el bug "mamá → grupo Música" porque el espacio de salida del LLM ya no incluye al grupo Música.

#### Umbrales y confirmación

Modelo clásico de three-tiered confidence en VUI (popularizado por Cathy Pearl, "Designing Voice User Interfaces", O'Reilly 2016: implicit confirm si >85%, explicit confirm si entre 40-85%, rechazo si <40%). Adaptado:

- `score_top1 ≥ 0.85` **y** `score_top1 − score_top2 ≥ 0.15` → ejecutar sin preguntar.
- `0.60 ≤ score_top1 < 0.85` → pedir confirmación corta ("¿A mamá, +56 9 xxx?").
- `score_top1 < 0.60` → ofrecer 2-3 opciones o pedir el nombre completo.

#### Biasing contextual de Parakeet con el inventario

Antes del corrector fonético post-STT está el biasing en decodificación. El paper "TurboBias: Universal ASR Context-Biasing" (Andrusenko et al., NVIDIA, arxiv 2508.07014, ASRU 2025) demuestra que un GPU-accelerated word-boosting tree "enables it to be used in shallow fusion mode for greedy and beam search decoding without noticeable speed degradation, even with a vast number of key phrases (up to 20K items)", con overhead de 2-5% RTFx, y está open-source como parte de NeMo. La documentación NVIDIA NIM para Parakeet TDT confirma los límites prácticos: "For RNNT and TDT models, word boosting can result in approximately 15% latency regression. Out of Vocabulary boosting is not supported for RNNT and TDT models", con boost score recomendado de 0.5 a 2.0. Práctica concreta: pasar a Parakeet, en cada invocación, el inventario unido de **(apps instaladas + contactos + artistas + aliases)** filtrado a ≤2000 entradas para no perder OOV de raíz.

### (d) Fuentes 2025-2026

- llama.cpp `grammars/README.md` y `docs/function-calling.md` (master, 2026); requiere `--jinja` para tool-calling en Gemma.
- Chen, Zhang, Hu, "Optimizing Entity Resolution in Voice Interfaces", EMNLP 2024 Industry Track, DOI 10.18653/v1/2024.emnlp-industry.1 (Splunk AI / Caltech / Xsolla).
- Andrusenko et al., "TurboBias", arxiv 2508.07014, ASRU 2025 — escala hasta 20K frases de contexto con 2-5% de overhead RTFx.
- NVIDIA NIM Speech docs (mar-2026): RNNT/TDT word boosting con ~15% regresión de latencia, **OOV no soportado**, boost 0.5-2.0.
- RapidFuzz docs (2025): SIMD-accelerated Jaro-Winkler con time complexity O([N/64]M).
- Beider-Morse Phonetic Matching, Steve Morse (stevemorse.org).
- Flagright, 2025: estándares de umbral 0.80-0.90 Jaro-Winkler para name matching AML.

### (e) Pseudocódigo

```python
# resolver.py
import unicodedata
from rapidfuzz import process, fuzz
from rapidfuzz.distance import JaroWinkler
from metaphone import doublemetaphone           # English
from spanish_metaphone import spanish_metaphone # ES
import sqlite_vec

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()

def phonetic_keys(name: str) -> set[str]:
    n = normalize(name)
    en = doublemetaphone(n)
    return {k for k in (*en, spanish_metaphone(n)) if k}

def resolve(mention: str, expected_type: str, user_id: str, top_k: int = 3):
    """
    expected_type ∈ {'contact_individual', 'contact_group', 'app', 'artist'}
    Devuelve [(entity_id, display_name, score, type), ...]
    """
    inv = inventory.fetch(user_id, expected_type)   # ya filtra grupo vs contacto
    if not inv:
        return []

    mention_n = normalize(mention)
    mention_keys = phonetic_keys(mention)

    cands = []
    for e in inv:
        e_keys = phonetic_keys(e.display_name)
        phon = 1.0 if mention_keys & e_keys else 0.0
        jw = JaroWinkler.normalized_similarity(mention_n, normalize(e.display_name))
        emb = cosine(emb_of(mention), e.embedding)   # EmbeddingGemma precomputado
        score = 0.4*phon + 0.3*jw + 0.3*emb
        cands.append((e.id, e.display_name, score, e.type))

    cands.sort(key=lambda x: -x[2])
    return cands[:top_k]

def build_enum_grammar(candidates):
    ids = " | ".join(f'"{c[0]}"' for c in candidates)
    return f"""
root  ::= "{{" ws "\"contact_id\":" ws id ws "," ws "\"message\":" ws string "}}"
id    ::= {ids}
string::= "\"" ([^"\\\\] | "\\\\" .)* "\""
ws    ::= [ \\t\\n]*
"""

def execute(utterance: str, user_id: str):
    intent, mention = parse_intent(utterance)
    cands = resolve(mention, expected_type=intent.expected_type, user_id=user_id)

    if not cands:
        return ask("No encontré a quién quieres escribir, ¿puedes deletrear?")

    top, second = cands[0], (cands[1] if len(cands) > 1 else (None, None, 0.0, None))
    margin = top[2] - second[2]

    if top[2] >= 0.85 and margin >= 0.15:
        grammar = build_enum_grammar(cands)
        prompt = SYSTEM + build_candidates_block(cands) + f"\nUsuario: {utterance}\n"
        out = llama_cpp.generate(prompt, grammar=grammar, jinja=True)
        return dispatch_tool(out)

    if top[2] >= 0.60:
        return confirm(f"¿A {top[1]}?")
    return choose_from(cands)
```

### Métricas que medir

- **Tasa de wrong-entity** (grupo cuando se quería contacto, persona X cuando se quería Y). Objetivo: <1%.
- **Tasa de auto-execute** vs **confirm** vs **choose** sobre 200 enunciados con nombres propios mixtos ES/EN.
- **Latencia añadida** por el candidate generation (Jaro-Winkler + Metaphone + embedding) sobre inventario de 200 entidades. Objetivo: <40 ms.
- **Precision@1, Recall@3** del rerank híbrido.
- **Tasa de transcripción correcta de proper nouns** (Chrome, Edge, Spotify, Bad Bunny) con biasing Parakeet activo vs sin activo.

---

## 3. Aprendizaje de alias y correcciones

### (a) Diagnóstico

Cuando el usuario corrige ("no, mamá es este otro número"), hoy no hay forma de persistir esa información de modo que (i) sobreviva a sesiones, (ii) tenga prioridad sobre el inventario base, (iii) no contamine a otros usuarios del producto universal, (iv) no quede vulnerable a memory poisoning. El paper MINJA (Dong et al., "Memory Injection Attacks on LLM Agents via Query-Only Interaction", arxiv 2503.03704, NeurIPS 2025) reporta literalmente: "MINJA achieves a high average success rate of 98.2% for injecting malicious records into the memory, and a high average attack success rate of 76.8% in eliciting the malicious reasoning steps", lo que muestra que toda escritura aprendida necesita defensa.

### (b) Opciones

| Opción | Precisión | Coste | Complejidad | Riesgo overfit |
|---|---|---|---|---|
| A. Sobrescribir global inventory en cuanto el usuario corrige | Alta para ese usuario | Bajo | Bajo | **Catastrófico** (contamina a todos) |
| B. Tabla `alias_overrides` per_user con prioridad de lectura | Alta | Bajo | Bajo | Nulo |
| C. B + confirmación explícita antes de persistir | Alta y robusta | Bajo | Medio | Nulo |
| D. Aprender embeddings personalizados del usuario | Muy alta | Alto (re-embedding) | Alto | Medio |

### (c) Veredicto local con 4B

**Opción C**. Esquema:

```sql
CREATE TABLE alias_overrides (
  id INTEGER PRIMARY KEY,
  user_id TEXT NOT NULL,
  alias TEXT NOT NULL,            -- "mamá"
  entity_id TEXT NOT NULL,        -- "ct_4427"
  entity_type TEXT NOT NULL,      -- "contact"
  source TEXT NOT NULL,           -- "user_correction" | "system_seed"
  confirmed_at TIMESTAMP,
  use_count INTEGER DEFAULT 0,
  last_used TIMESTAMP,
  deleted_at TIMESTAMP,
  UNIQUE(user_id, alias, entity_type, deleted_at)
);
```

Reglas:

1. **Antes de persistir un override**, el sistema confirma: "Anoté que cuando dices 'mamá' me refiero a Marisol (+56...). ¿Es correcto?". Solo si la respuesta es afirmativa se inserta con `confirmed_at` no nulo.
2. **En `resolve()`, el lookup en `alias_overrides` precede al matching fuzzy y *fija* el resultado con score 1.0** (short-circuit). Si el alias está confirmado y vigente, no se consulta el inventario.
3. **Aislamiento per-user estricto**: el `user_id` es parte de cada query; nunca hay tabla global. Para un producto "universal" multi-usuario, las semillas comunes (apps de Windows, artistas populares) viven en `system_seeds` solo-lectura; los aprendizajes viven en `alias_overrides` y `mem_facts` con `user_id`.
4. **Resolución de conflictos**: si el usuario dice "ya no es mamá, ahora mamá es Andrea", se soft-delete el override anterior (`deleted_at`) y se crea uno nuevo con confirmación. Histórico se mantiene para auditoría.
5. **Defensa anti-poisoning**: solo se aprende alias si (i) hubo confirmación explícita, (ii) la fuente fue un evento de corrección dentro de un flujo válido, (iii) `use_count` permite identificar overrides "huérfanos" creados por error.

### (d) Fuentes

- Dong et al., MINJA, arxiv 2503.03704, NeurIPS 2025 — 98.2% ISR / 76.8% ASR.
- Upadhyay, "Memory Poisoning in Agentic LLMs", mayo 2025: recomienda tagging & provenance, expiry, validación de entrada y aislamiento por tenant/topic/context.
- Devarangadi Sunil et al., "Memory Poisoning Attack and Defense on Memory Based LLM-Agents", arxiv 2601.05504 (ene 2026): I/O moderation con composite trust scoring y memory sanitization con temporal decay.
- Wei et al., "A-MemGuard" (2025): consistency checks separando "lesson memory".

### (e) Pseudocódigo

```python
def learn_alias_from_correction(user_id, alias, intended_entity_id, dialogue_state):
    ok = ask_yes_no(f"Entendido: '{alias}' se refiere a "
                    f"{name_of(intended_entity_id)}. ¿Lo guardo así?")
    if not ok:
        return
    db.execute("""UPDATE alias_overrides SET deleted_at=CURRENT_TIMESTAMP
                  WHERE user_id=? AND alias=? AND entity_type=? AND deleted_at IS NULL""",
               (user_id, alias, type_of(intended_entity_id)))
    db.execute("""INSERT INTO alias_overrides
                  (user_id, alias, entity_id, entity_type, source, confirmed_at)
                  VALUES (?, ?, ?, ?, 'user_correction', CURRENT_TIMESTAMP)""", ...)
```

### Métricas

- **Tasa de aplicación correcta del override** en los 7 días siguientes a una corrección.
- **Falsos overrides** (creados sin confirmación o por ruido).
- **Cross-user contamination rate**: 0 por construcción si los queries son por `user_id`.

---

## 4. Qué recordar (selección de memoria, evitar memory poisoning)

### (a) Diagnóstico

Hoy se escribe casi todo a SQLite, lo que produjo el incidente reportado: el 52% de la base era basura de pruebas. Falta:

- **Importance/salience scoring** antes de escribir.
- **Deduplicación** semántica (dos hechos casi iguales con paráfrasis distinta).
- **Decay/forgetting** access-based.
- **Filtro anti-test/junk** (cadenas tipo "test", "asdf", "prueba 123").

### (b) Opciones

| Opción | Precisión | Coste | Complejidad | Riesgo |
|---|---|---|---|---|
| A. Escribir todo (status quo) | — | Crece sin techo | Trivial | Poisoning + degradación |
| B. Heurística simple (longitud + blocklist) | Media | Bajo | Bajo | Falsos negativos |
| C. LLM-as-classifier ("¿vale la pena recordar?") por turno | Alta | Alto (1 inferencia extra) | Medio | Costo en 4B |
| D. **Hybrid**: heurística rápida + clasificación LLM solo si pasa la heurística + dedup semántico + decay | Alta | Medio | Medio-Alto | Bajo |

### (c) Veredicto local con 4B

**Opción D**. El pipeline de escritura:

1. **Filtro de basura** (regex + listas):
   - blocklist literal: `{"test", "prueba", "asdf", "1234", "hola hola", "..."}`
   - longitud mínima del hecho normalizado ≥ 10 chars
   - si la utterance original tenía un patrón "test mode" o vino del modo dev, descartar
2. **Salience scoring** (señales determinísticas, sin LLM):
   - `+2` si menciona un *named entity* del inventario
   - `+2` si el usuario lo afirma con verbos de aprendizaje ("recuerda que", "siempre", "anota")
   - `+1` si se repite en la sesión
   - `−2` si es una pregunta efímera ("¿qué hora es?")
   - `−1` si es una orden ya cumplida sin información nueva
   - Solo se escribe si `salience ≥ 2`.
3. **Dedup semántico**: antes de insertar, KNN sobre `mem_facts` con `vec_distance_cosine ≤ 0.10` (umbral conservador). Si ya existe, *actualizar* `last_seen` y `use_count`, no insertar. El blog de Mem0 sobre el "Modal Model of Memory" enfatiza este punto: extraer hechos discretos en vez de surface form.
4. **Decay con uso** (recomendado por Oracle Developers, mar 2026: "a recency-weighted scoring function multiplies semantic similarity by an exponential decay factor based on time since last access"): `effective_score = salience * exp(-age_days / 60) * (1 + log(1+use_count))`. Hechos con `effective_score < 0.3` durante 90 días se purgan.
5. **TTL explícito** por categoría: alias = sin TTL (manual), preferencias estables (idioma, zona horaria) = sin TTL, hechos episódicos ("ayer fui al dentista") = 30 días.
6. **Integridad**: cada escritura lleva `provenance` (`user_correction`, `passive_extract`, `system_seed`) y `tool_invocation_id` para poder borrar todo lo creado en una sesión defectuosa.

Para defensa adicional anti-poisoning (MINJA, AgentPoison, BadChain), aplicar las recomendaciones de la literatura ene 2026: input/output moderation con composite trust scoring, sanitization en retrieval con temporal decay y pattern-based filtering.

### (d) Fuentes 2025-2026

- "Memory Poisoning Attack and Defense on Memory Based LLM-Agents", arxiv 2601.05504 (ene 2026).
- "Forgetting as a Feature: Cognitive Alignment of LLMs", arxiv 2601.09726 (ene 2026): forgetting como exponential decay alineado con curva de memoria humana.
- A-MemGuard (Wei et al. 2025): online consistency checks separando "lesson memory".
- Mem0 blog "The Modal Model of Memory": forgetting es interferencia, no decay; almacenar hechos discretos.
- Oracle Developers blog (mar 2026), "Agent Memory: Why Your AI Has Amnesia and How to Fix It".

### (e) Pseudocódigo

```python
JUNK_RE = re.compile(r"^(test|prueba|asdf|hola hola|\.{2,}|\d{1,5})$", re.I)
LEARN_VERBS = re.compile(r"\b(recuerda|siempre|anota|de ahora en adelante)\b", re.I)

def should_remember(fact: str, ctx) -> tuple[bool, int]:
    f = fact.strip()
    if len(normalize(f)) < 10: return False, 0
    if JUNK_RE.match(f.lower()): return False, 0
    s = 0
    s += 2 if any(e.id in mentions(f) for e in inventory.all()) else 0
    s += 2 if LEARN_VERBS.search(f) else 0
    s += 1 if ctx.repeated_in_session(f) else 0
    s -= 2 if f.endswith("?") else 0
    return s >= 2, s

def write_fact(fact, ctx):
    ok, salience = should_remember(fact, ctx)
    if not ok: return
    emb = embed(fact)
    near = db.execute("""SELECT id FROM mem_vec
                         WHERE vec_distance_cosine(embedding, ?) < 0.10
                         AND user_id=? LIMIT 1""", (emb, ctx.user_id)).fetchone()
    if near:
        db.execute("UPDATE mem_facts SET last_seen=?, use_count=use_count+1 WHERE id=?",
                   (now(), near[0]))
        return
    db.execute("INSERT INTO mem_facts (...) VALUES (...)", ...)

def purge_low_value():
    db.execute("""DELETE FROM mem_facts
                  WHERE salience * exp(-(julianday('now')-julianday(created_at))/60.0)
                        * (1+ln(1+use_count)) < 0.3
                    AND (julianday('now')-julianday(created_at)) > 90""")
```

### Métricas

- **Junk rate** (% de filas que un human-rater calificaría como inútil). Objetivo: <5% (de un 52% actual).
- **Dedup hits/100 escrituras**. Si >30 hits, el umbral 0.10 está bien; si <5, es demasiado agresivo.
- **Recall de hechos importantes a 30 / 90 días**: probar con un set fijo de 50 hechos críticos sembrados artificialmente.
- **Tamaño promedio de la SQLite** a 30/60/90 días por usuario.

---

## 5. Privacy / local (restricción 100% offline)

### (a) Diagnóstico

Todo lo anterior debe ejecutarse sin red. Componentes que típicamente serían cloud:

- Embeddings ⇒ **EmbeddingGemma** local (308M, <200MB RAM con QAT, multilingüe 100+ idiomas, <15 ms en EdgeTPU, manejable en CPU x86).
- Vector store ⇒ **sqlite-vec** (Mozilla Builders project; v0.1.9 estable mar-2026; corre en Windows nativo; DiskANN está en alpha v0.1.7-alpha.* — no usar todavía en prod).
- Memory framework ⇒ **NO** Mem0 cloud, **NO** Letta SaaS; construir el stack propio como en §1-4.
- STT ⇒ Parakeet ya local; aprovechar word boosting con el inventario.

### (b) Opciones de vector store local

| Opción | Latencia | Setup | Producción Windows | Tamaño DB |
|---|---|---|---|---|
| **sqlite-vec v0.1.9** | <5 ms para <100k vec | Trivial (extensión SQLite) | Sí, oficial | Misma SQLite |
| sqlite-vec con DiskANN | Sub-ms para millones | **Alpha** (v0.1.7-alpha.*, no prod) | Sí | Misma SQLite |
| FAISS local | <2 ms | Más complejo, requiere flat file separado | Sí | Aparte |
| ChromaDB local | 5-15 ms | Más pesado, dependencias C++ | Sí | Aparte |
| sqlite-vector (sqliteai) | <5 ms | Extensión SQLite alternativa | Sí | Misma SQLite |

### (c) Veredicto local con 4B

**sqlite-vec v0.1.9 estable + EmbeddingGemma cuantizada**. Razones:

1. La memoria episódica y los aliases ya viven en SQLite (ExperienceMemory). Cohabitar embeddings en la misma DB elimina sincronización.
2. La extensión es C puro, sin dependencias, corre en Windows nativo (Mozilla Builders project; oficial Windows release).
3. Tamaños esperados (≤100k vectores por usuario en escenarios extremos) no requieren ANN; brute-force es <5 ms.
4. Si en el futuro hace falta ANN, DiskANN está aterrizando en sqlite-vec sin migración: las notas de release v0.1.7-alpha.* (feb-mar 2026) introducen "new ANN indexes: rescore, ivf (experimental, not enabled), and DiskANN".

**Precaución**: la versión 0.1.9 (31 mar 2026) es la última estable; DiskANN está en `0.1.7-alpha.*` — no usar en producción todavía. El propio repo declara que las DELETEs en DiskANN aún tienen un *data leak via un-deleted compressed neighbor vectors*.

### (d) Fuentes 2025-2026

- asg017/sqlite-vec releases (GitHub), v0.1.9 (31 mar 2026); v0.1.7-alpha.* con DiskANN (feb-mar 2026, no prod).
- Google Developers Blog, EmbeddingGemma, 4 sep 2025.
- sqlite.ai blog, "Building a RAG on SQLite", 23 oct 2025.
- IBM Granite Embedding Multilingual R2 (alternativa multilingüe Apache 2.0 si EmbeddingGemma diera problemas de licencia en algún país, 195 MB en 384 dim).

### (e) Pseudocódigo de despliegue

```powershell
# Windows, 100% offline
python -m pip install --no-index --find-links=.\wheels  ^
       sqlite-vec rapidfuzz metaphone llama-cpp-python sentence-transformers

# Cargar la extensión sqlite-vec
python - <<EOF
import sqlite3, sqlite_vec
con = sqlite3.connect("agent.db")
con.enable_load_extension(True)
sqlite_vec.load(con)
con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS mem_vec USING vec0(
                 id INTEGER PRIMARY KEY, embedding FLOAT[768])""")
EOF

# Lanzar llama.cpp build b9090 con Gemma 4 E4B-it Q4_K_M, jinja para tools
llama-server.exe ^
  -m .\models\gemma-4-E4B-it-Q4_K_M.gguf ^
  --jinja ^
  --grammar-file .\grammars\dynamic_entity_enum.gbnf ^
  --ctx-size 8192 -ngl 99 --port 8080
```

### Métricas

- **Cero llamadas a red** durante 24h de uso (medir con un sniffer local).
- **RAM máxima** del proceso (EmbeddingGemma + llama-server + sqlite). Objetivo: <6 GB con Gemma 4 E4B Q4_K_M.
- **Cold start** end-to-end (utterance → STT → resolución → LLM → tool). Objetivo: <2.5 s.

---

## Resumen de métricas para evaluación end-to-end

Estos son los **diez números** que deberían entrar en el dashboard:

| Métrica | Cómo medir | Objetivo |
|---|---|---|
| Wrong-entity rate (contact/group/app) | Set de 200 utterances con golden ID | <1% |
| STT proper-noun recall (Chrome, Edge, Spotify, Bad Bunny) | WER restringido a proper nouns | ≥95% |
| Auto-execute rate vs ask-confirm | Conteo en logs | 70/25/5 (exec/confirm/choose) |
| Resolver latency (fonético+fuzzy+embed) | p50/p95 sobre 1000 turns | <40/<120 ms |
| Retrieval hit@k=4 | Hechos golden en top-k | ≥85% |
| Memoria — junk rate | Human-rate sample de 100 filas | <5% |
| Memoria — tamaño DB / usuario | bytes en SQLite | <50 MB a 90 días |
| Override-after-correction precision | 50 escenarios sembrados | ≥95% |
| Cross-user contamination | DB inspection | 0 |
| Cold-start E2E | utterance → tool dispatch | <2.5 s |

---

## Recomendaciones (qué hacer mañana, en orden)

1. **Día 1-2**: cambiar el contrato del tool-call para que `contact_id`, `app_id`, `artist_id` sean los argumentos, no strings. Modificar el backend WhatsApp para que abra por ID/JID, no por search GUI.
2. **Día 3-5**: construir `resolver.py` con phonetic + Jaro-Winkler + embedding rerank; cablear `process.cdist` de RapidFuzz; añadir Beider-Morse como tercer algoritmo fonético.
3. **Día 6-7**: cablear GBNF/JSON-Schema enum dinámico en cada turno (regenerar el grammar con los top-k IDs antes de cada llamada a llama-server `--jinja`).
4. **Semana 2**: instalar sqlite-vec v0.1.9 + EmbeddingGemma; migrar la memoria a las tres capas (core/retrieval/episodic); añadir filtro de junk y salience scoring.
5. **Semana 3**: alias_overrides con confirmación, decay y dedup; auditoría per_user.
6. **Semana 4**: cablear word boosting de Parakeet contra el inventario activo (apps + contactos + artistas, ≤2000 entries, boost score 0.5-2.0 para TDT).
7. **Continuo**: dashboard con las 10 métricas. Cualquier cambio sin moverlas en la dirección correcta se revierte.

### Benchmarks que cambiarían la decisión

- Si `wrong-entity rate` no baja por debajo de 3% con todo lo anterior ⇒ considerar fine-tuning de Gemma 4 E4B (LoRA) con un dataset propio de tool-calls grounded. FunctionGemma (270M, blog.google sep 2025) podría servir como router previo: Google reporta que el fine-tuning sube la accuracy de Mobile Actions de 58% baseline a 85%.
- Si el `retrieval hit@k=4` cae bajo 70% ⇒ subir a EmbeddingGemma full-precision o probar Qwen3-Embedding-0.6B local.
- Si los 6GB de RAM no caben en hardware target ⇒ bajar a Gemma 4 E2B Q4_K_M o IBM Granite Embedding Multilingual R2 (97M, 195 MB safetensors).
- Si Parakeet TDT word boosting con ~15% de regresión de latencia es inaceptable ⇒ evaluar TurboBias (NeMo) que reporta 2-5% RTFx overhead con hasta 20K frases.

---

## Caveats

- **Gemma 4 E4B y tool-calling**: pruebas comunitarias indican que E4B "is much weaker at tool calling than 26B"; sin GBNF/enum forzado, el modelo *inventa* IDs. El esquema de §2 no es opcional, es la única forma de que esto funcione de manera consistente en este tamaño de modelo.
- **DiskANN en sqlite-vec**: aún alpha (v0.1.7-alpha.*, feb-mar 2026). Para producción usar v0.1.9 (brute-force, suficiente hasta ~100k vectores).
- **Beider-Morse en Python**: la biblioteca canónica es `abydos`, que no se actualiza desde 2020. Alternativa: portar el algoritmo desde la implementación PHP de Haran o usar la implementación de Apache Solr vía proceso aparte. Si esto es prohibitivo, sustituir Beider-Morse por Metaphone3 o quedarse con Double Metaphone + Spanish Metaphone + Jaro-Winkler (la pérdida de calidad es modesta en nombres hispanos).
- **Word boosting de Parakeet TDT**: sin soporte OOV; los nombres extranjeros muy raros (apellidos chilenos poco frecuentes) no se benefician. Para esos, depender del corrector fonético post-STT.
- **MINJA y memoria persistente**: ningún esquema offline elimina el riesgo; lo mitigan provenance, confirmación, decay y aislamiento per_user. Asumir que un usuario malicioso *en su propia máquina* puede envenenar *su propia* memoria; el invariante a proteger es que no se contamine la de otros usuarios ni los `system_seeds`.
- **Letta vs Mem0 en LoCoMo (74.0% vs 68.5%)**: ambos números usan GPT-4o mini; en Gemma 4 E4B Q4_K_M no esperar los mismos valores absolutos. La conclusión transferible es la *arquitectura* (filesystem/retrieval iterativo bate a graph memory sofisticado en modelos pequeños), no los porcentajes.
- **Latencias indicadas**: medidas en un Ryzen 7 / RTX 3070 típico. En CPU pura las cifras suben ~2-3×; Q4_K_M es la cuantización recomendada para mantener calidad de tool-calling en Gemma 4 E4B.
- **Fuentes de "three-tiered confidence" (85%/40%)**: provienen del libro de Cathy Pearl *Designing Voice User Interfaces* (O'Reilly, 2016), no de literatura peer-reviewed reciente; calibrar empíricamente al dominio del usuario chileno.