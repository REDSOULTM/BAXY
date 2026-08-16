# Prompt de Investigación — Optimización Máxima del LLM en Carter v4

## Contexto del proyecto

Estoy construyendo **Carter v4**, un asistente local Jarvis-style que corre en Windows + Ollama, con presupuesto de latencia "Alexa-tier" (3-8s en chat trivial, 5-12s en tools, 12-20s en apps). El sistema tiene un loop ReAct single-thread, 47 tools registradas, 75 unit tests verde, una matrix de 540 casos oficiales (18 categorías × 30 casos), y actualmente sale a 472/540 PASS auto (~510/540 manual). El modelo elegido tras research previa es:

**`qwen3:4b-instruct-2507-q4_K_M`**

(non-thinking nativo, 2.5GB Q4_K_M, ~256K context window soportado por el modelo aunque uso `num_ctx=8192` por VRAM). Hardware: RTX 4060 Ti, 15-16GB VRAM. ContextoCarter.md exige local + privado, no cloud, no per-app hardcodes, no keyword lists per idioma, universal multilingüe.

Ahora necesito **optimizar al máximo el LLM** para sacarle el último 10% de rendimiento posible sin cambiar de modelo. Quiero saber **TODO** lo que se puede afinar.

---

## Lo que necesito que investigues a fondo

### 1. Sampling parameters — el set óptimo para Hermes-style tool calling

Hoy uso `temperature=0.1`, `repeat_penalty=1.1`. ¿Es lo correcto para qwen3:4b-instruct-2507? Investigá:

- ¿Qué `temperature`, `top_p`, `top_k`, `min_p`, `repeat_penalty`, `repeat_last_n`, `mirostat`, `mirostat_eta`, `mirostat_tau`, `presence_penalty`, `frequency_penalty`, `tfs_z`, `typical_p` recomiendan los autores de Qwen3 para tool-use determinístico?
- ¿Hay benchmarks BFCL v3 o BBoN comparando combos? El paper de Qwen3 técnico, los model cards en Ollama y HF, blogs como llama.cpp/ollama issues.
- Para **emisión de `<tool_call>` JSON estructurado**, ¿qué combo da mayor parse rate?
- Para **explicaciones de conocimiento sin tool**, ¿qué combo mantiene fluidez sin alucinar?
- Para **idioma multilingüe** (ES/EN), ¿hay setting que mejore consistencia?
- Recomendá un **set "principal"** y un **set "destructive-strict"** (cuando se pide tool destructiva, queremos máxima determinismo).

### 2. KV cache, FlashAttention y prefix caching

- `OLLAMA_KV_CACHE_TYPE=q8_0` vs `f16` vs `q4_0`: comparativa real en quality vs VRAM saved.
- `OLLAMA_FLASH_ATTENTION=1` con qwen3:4b: ¿está soportado? ¿Speedup real medido?
- **Prefix caching** de Ollama: cómo invocarlo correctamente. ¿Es automático? ¿Necesito mantener el system message byte-a-byte estable? ¿Cómo verificar que está cacheando?
- ¿Hay flags adicionales `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_NEW_ENGINE` que ayuden a Carter?
- **Quantization tradeoffs**: ¿conviene usar `q5_K_M`, `q6_K`, `q8_0` en vez de `q4_K_M`? Latencia vs quality.

### 3. Context window y compaction — sweet spot real

Hoy uso `num_ctx=8192`. ¿Es óptimo?

- Para qwen3:4b-instruct-2507, ¿cuál es la longitud de contexto donde la quality empieza a degradar? (long-context degradation curve)
- ¿Hay benchmarks específicos de Qwen3 sobre needle-in-haystack a 16k, 32k, 64k, 128k?
- **KV cache memory**: cuánto VRAM extra consume cada token de contexto en q4_K_M vs q8_0 cache.
- ¿Conviene `num_ctx=4096` para chat trivial y `num_ctx=16384` para misiones largas, o un único `num_ctx`?
- Compaction strategy: ¿cuál es el best practice — resumir con el mismo modelo, mantener últimos N turns, hybrid? ¿Existe alguna estrategia "rolling summary" óptima?

### 4. System prompt — tokens budget y estructura óptima

Mi prompt v10 tiene ~800 tokens. ¿Es eficiente?

- Para qwen3:4b, ¿hay un sweet spot de longitud de system prompt? Pasada cierta longitud el modelo "olvida" reglas.
- ¿Hay forma de estructurar el prompt para maximize attention? (e.g. reglas críticas al inicio vs al final, formato XML vs Markdown vs JSON)
- ¿Cómo se compara few-shot examples (1-3) vs zero-shot en tool-use accuracy?
- ¿Los modelos Qwen3-Instruct-2507 fueron entrenados con un prompt template específico? ¿Lo estoy respetando?
- ¿Se beneficia de "thinking" prompts (chain-of-thought injection en instructions) o eso degrada porque es non-thinking?

### 5. Function calling format — Hermes vs OpenAI vs Qwen native

Hoy uso Hermes-style XML `<tool_call>{json}</tool_call>` parseable por Ollama. ¿Hay opciones mejores?

- Qwen3 oficialmente publicó un **Qwen-Agent format**: investigar si Ollama lo soporta y si tiene mejor parse rate.
- `format: "json"` vs `response_format: {type: "json_schema"}` en Ollama: ¿cómo funcionan con tools? ¿Aceleran o ralentizan?
- **GBNF grammar-constrained decoding** (llama.cpp): cómo activar en Ollama, costo en latencia, ¿garantiza JSON válido?
- Cuando se le pasan **47 tools al catálogo**, ¿el modelo se confunde? ¿Hay estrategia de retrieval de tools (top-K relevantes) común?
- ¿Cómo escribir las descriptions de tools para máxima clarity? ¿length óptimo? ¿estilo (acción vs descripción)?

### 6. Latencia per-token y first-token latency

- ¿Cuál es la latencia esperada de qwen3:4b en RTX 4060 Ti 16GB? Tokens/segundo de generación + first-token-time.
- Diferencia entre primer call (cold) y siguientes (warm) con `keep_alive=-1`.
- ¿Hay forma de **acelerar el first-token** específicamente? (es lo que más impacta percepción "Alexa")
- **Speculative decoding** con qwen3:0.6b o qwen3:1.7b como draft model: ¿funciona en Ollama? ¿Speedup real? ¿Vale la pena la VRAM extra?

### 7. Batching, paralelismo y throughput (si es relevante para Carter)

Carter actualmente es single-user single-turn. Pero la matrix corre 540 casos secuenciales.

- ¿Vale la pena `OLLAMA_NUM_PARALLEL=2` para procesar paralelo en testing? Tradeoff con latencia per-call.
- ¿`OLLAMA_NUM_THREAD` afecta? Default es CPU-detect.

### 8. Modo no-thinking explícito

qwen3:4b-instruct-2507 ya es non-thinking nativo. Pero qwen3 base puede activar thinking via `/no_think` toggle o `enable_thinking=False`. Investigar:

- ¿Hay forma de activar thinking transparentemente en este modelo si lo quisiera para casos compositional reasoning (C14 misiones)?
- O al revés: ¿hay forma de hacerlo aún MÁS rápido (skip más layers, etc.)?
- **Stop tokens custom**: ¿hay tokens que pueda configurar para cortar generación temprano cuando Carter detecta cierre de respuesta?

### 9. Streaming y UX

Hoy Carter en CLI y eventualmente UI espera el reply completo. ¿Conviene activar `stream=True`?

- Trade-off: latencia percibida vs complejidad de parsing tool_calls (que solo aparecen al final).
- ¿Algún truco para mostrar el reply mientras se siguen generando tools en multi-step?

### 10. Configuraciones específicas de Ollama

- `OLLAMA_MODELS` directory: ¿afecta perf si está en SSD vs HDD?
- `OLLAMA_DEBUG`, logs: cómo activar para detectar cuellos de botella reales (eval/load/sample timings).
- `OLLAMA_REQUEST_TIMEOUT`: default y override óptimo.
- Diferencias entre **Ollama nativo** y **Ollama+llama-server backend**: ¿hay forma de bypass Ollama y hablar directo con llama-server para más control?

### 11. Optimizaciones específicas a Carter v4

Dado que Carter:
- Tiene 47 tools en el catálogo
- Usa Hermes XML tool format
- Tiene system prompt ~800 tokens
- Necesita responder en <8s para chat trivial
- Lleva un loop ReAct con max 3 niveles de cadena

¿Qué optimizaciones **específicas** se podrían aplicar?

- ¿Conviene tener **dos system prompts** (chat-mode más corto, tool-mode con catálogo)?
- ¿Conviene **filtrar el catálogo de tools** dinámicamente (top-K) por turno?
- ¿Conviene un **modelo más chico** (qwen3:1.7b o qwen3:0.6b) para router/intent y solo escalar a 4b para acciones complejas?

### 12. Comparativa de versions: qwen3:4b vs alternatives en mismo tier

Aunque YA elegí qwen3:4b-instruct-2507-q4_K_M, compará brevemente:

- `qwen3:4b-instruct-2507-q5_K_M` / `q6_K` / `q8_0` — quality vs latencia tradeoff
- Modelos similares de otros vendors (Phi-4-mini-instruct, Granite 4.x 4B, Llama-3.2-3B-Instruct, Gemma-2-2b) — ¿alguno superior en BFCL/IFEval ES?
- Si en 6 meses sale un qwen3.5:4b o qwen4:4b, ¿qué características debo monitorear para upgrade?

---

## Formato de la respuesta esperada

Quiero que devuelvas:

1. **TL;DR** (top 5-7 cambios concretos a aplicar HOY) con esfuerzo y impacto estimado.
2. **Tabla de parámetros recomendados** con valores específicos para sampling, KV cache, env vars de Ollama.
3. **Sección por sección** (1-12 arriba) con respuestas concretas, citando papers/docs/issues cuando sea posible.
4. **Caveats**: cosas que la documentación afirma pero que en práctica no se sostienen, y cosas que dependen de hardware específico.
5. **Roadmap**: orden recomendado de aplicación (qué cambiar primero, qué medir, qué cambios son seguros vs riesgosos).

**Importante**: NO me digas cosas genéricas tipo "depende del caso de uso". Quiero **valores concretos** con justificación. Si no estás seguro, decílo explícitamente y propone cómo medirlo.

**Restricciones que NO se pueden violar**:
- Local + privado (no llamadas a cloud APIs)
- No cambiar de modelo (qwen3:4b-instruct-2507-q4_K_M se queda)
- Latencia objetivo Alexa-tier (3-8s simple)
- Compatible con Ollama (no migrar a vLLM/TabbyAPI/ExLlamaV2 ahora)
- Universal sin keyword lists per idioma

---

Si tenés acceso a búsquedas web, usá los recursos más recientes (2025-2026):
- Qwen3 model card en HuggingFace
- Ollama issues/discussions
- llama.cpp performance benchmarks
- BFCL leaderboard
- Papers de Qwen2.5/3, paper "Llama 3 herd of models", técnicas de FastAttention, etc.

Reporte detallado pero conciso (~2000-4000 palabras). Foco en accionabilidad inmediata.
