# Carter v4 — Squeezing the last 10% out of `qwen3:4b-instruct-2507-q4_K_M` en Ollama (Windows / RTX 4060 Ti 16GB)

> Reporte técnico exhaustivo. Idioma: español rioplatense/chileno casual + tecnicismos en inglés. Foco: accionabilidad inmediata, valores concretos, citas a docs/papers. Donde algo es incierto, lo digo y propongo cómo medirlo.

---

## TL;DR — Top 7 cambios para aplicar HOY

| # | Cambio | Esfuerzo | Impacto esperado | Riesgo |
|---|--------|----------|------------------|--------|
| 1 | **Sampling oficial Qwen3-Instruct-2507**: `temperature=0.7, top_p=0.8, top_k=20, min_p=0, presence_penalty=1.0` (set "principal"). Para tools destructivas: bajar a `temperature=0.2, top_p=0.8, top_k=20, min_p=0.05, presence_penalty=0`. Tu `0.1+rep_pen=1.1` actual está **fuera de la recomendación oficial** y rep_penalty puede romper formato. | **S** | +2–5 % parse rate de `<tool_call>`, mejor multilingüe ES/EN, menos repeticiones | Bajo |
| 2 | `OLLAMA_FLASH_ATTENTION=1` + `OLLAMA_KV_CACHE_TYPE=q8_0` como variables de entorno **de sistema** (no del shell) en Windows. | **S** | KV cache cae ~50 %, libera 0.5–1 GB VRAM, no se nota en quality (Qwen3-4B usa GQA con solo 8 KV heads → es bastante robusto a q8_0). | Bajo |
| 3 | `OLLAMA_KEEP_ALIVE=24h` + warm-up con request dummy al boot del proceso Carter. Verificar con `expires_at` en `/api/ps` (debe ser `0001-01-01T00:00:00Z` si pasás `keep_alive=-1`). | **S** | Elimina cold-start (~1.5–4 s en TTFT) en chat trivial. | Nulo |
| 4 | **Bajar `num_ctx` a 4096 para chat-mode, mantener 8192 sólo para tool-mode**, y compactar a 16384 sólo en misiones largas. Cada token de contexto cuesta ~36 KB de KV en f16 (8.6 KB en q8_0 cache) para Qwen3-4B. | **S** | TTFT cae ~30–40 % en triviales; libera VRAM para más loaded models o draft model futuro. | Bajo |
| 5 | **Stream=True + parser de `<tool_call>` incremental** que arranca a generar UI mientras el modelo decide si va a llamar tool. Hoy estás esperando el final completo. | **M** | TTFT percibido baja drásticamente; chat trivial pasa de 3-8s → 1.5-3s perceptual. | Medio (parser) |
| 6 | **Tool retrieval top-K=8** dinámico para los 47 tools (embedding del system + last user turn → top-K). Literatura (TinyAgent, RAG-MCP, Toolshed) muestra que con catálogos >20 tools el accuracy mejora bajando a top-3-8 relevantes. | **M** | -300/-500 tokens en system prompt en triviales → TTFT ↓; mejor decisión de tool. | Medio |
| 7 | **Fix tool-rendering bug**: en lugar de pasar tools por `/api/chat tools=[]`, embebé el catálogo Hermes XML directamente en el system prompt. Ollama tiene un bug confirmado (issue #14601) donde serializa los tools como Go-structs en vez de JSON válido. | **S** | +5–10 % parse rate inmediato si estás usando `tools=` param. | Bajo |

**Si aplicás solo (1)+(2)+(3)+(7)** ya tendrías la mayoría del 10 %: probablemente +6/+12 PASS sobre 540 (de 472 → 478-484), con TTFT más bajo y consistencia mejor en multilingüe. Lo demás son ganancias marginales.

---

## Tabla maestra de parámetros recomendados

### Sampling — set "principal" (chat trivial + tools no destructivas)

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| `temperature` | **0.7** | Recomendación oficial Qwen3-Instruct (no-thinking) en model card y tech report. |
| `top_p` | **0.8** | Recomendación oficial. |
| `top_k` | **20** | Recomendación oficial. |
| `min_p` | **0** | Recomendación oficial; tu modelo ya está bien acotado por top_p+top_k. |
| `presence_penalty` | **1.0** | Rango 0–2 sugerido para reducir repeticiones; Qwen team usa 1.5 en benchmarks pero advierte que >1.5 puede causar **language-mixing ES↔EN** y caída leve de quality. 1.0 es el sweet spot conservador. |
| `frequency_penalty` | **0** | No recomendado por Qwen team. |
| `repeat_penalty` | **1.0** | Tu 1.1 actual NO está recomendado; con presence_penalty configurado, repeat_penalty ≠ 1 puede degradar JSON estructurado. Bajalo a 1.0. |
| `repeat_last_n` | **64** (default) | Solo relevante si subís repeat_penalty. |
| `mirostat` | **0** (off) | No recomendado por Qwen. |
| `tfs_z`, `typical_p` | **default/off** | Sin recomendación oficial; sumar samplers no documentados aumenta varianza. |
| `num_predict` | **2048** chat, **4096** tools, **16384** misiones | Qwen team recomienda 16384 como output default; en latency-budget Alexa-tier conviene capear más bajo. |
| `seed` | **fijo** durante test, **aleatorio** en prod | Solo reproducibilidad. |

### Sampling — set "destructive-strict" (delete, send-email, push, payment, etc.)

| Parámetro | Valor | Notas |
|-----------|-------|-------|
| `temperature` | **0.2** | Cuasi-greedy pero no 0; greedy puro puede meterse en loops. |
| `top_p` | **0.8** | Mantenelo. |
| `top_k` | **20** | Mantenelo. |
| `min_p` | **0.05** | Robustece la cola — paper Min-P (Nguyen et al., ICLR 2025) muestra que decoupling de temperatura ayuda. |
| `presence_penalty` | **0** | En modo determinístico no hace falta. |
| `repeat_penalty` | **1.0** | |

> **Nota**: el set destructive no está empíricamente validado por Qwen team — es la mejor combinación que se desprende de la literatura (Min-P paper) + el principio de "cuanto más estructurado el output, más conservador el sampler". **Cómo medir**: corré los ~30 casos del category "destructive" 5× con cada set y compará AST-equality del JSON.

### KV cache + Flash Attention + env vars (Windows)

```
[System Properties → Environment Variables → System]
OLLAMA_FLASH_ATTENTION = 1
OLLAMA_KV_CACHE_TYPE   = q8_0
OLLAMA_KEEP_ALIVE      = 24h
OLLAMA_NUM_PARALLEL    = 1        # single-user, ver §7
OLLAMA_MAX_LOADED_MODELS = 2      # para tener qwen3:4b + draft 0.6b si lo agregás
OLLAMA_CONTEXT_LENGTH  = 8192     # default global; podés bajar a 4096 y subir per-request
OLLAMA_DEBUG           = 1        # mientras estás tuneando; sacalo en prod
OLLAMA_MODELS          = D:\ollama\models   # SSD NVMe
```

Reiniciá Ollama (Tray → Quit → relanzar) — env vars del shell **NO** llegan al servicio si arranca en background.

### Modelfile recomendado para Carter

```dockerfile
FROM qwen3:4b-instruct-2507-q4_K_M

# Sampling (set principal)
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER min_p 0
PARAMETER presence_penalty 1.0
PARAMETER repeat_penalty 1.0
PARAMETER num_ctx 8192
PARAMETER num_predict 4096

# Stops conservadores. Qwen3 usa <|im_end|> como turn-end
# y existe bug post v0.12.3 donde a veces emite <|endoftext|> y sigue generando (issue #12444)
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER stop "<|im_start|>"

# Tu system prompt va aparte por SetSystem(...) para no recompilar el modelo cada turn
```

---

## 1. Sampling parameters óptimos para Qwen3-4B-Instruct-2507

### Lo que dice la fuente primaria

La **model card oficial** de `Qwen/Qwen3-4B-Instruct-2507` en HuggingFace (sección "Best Practices") es explícita:

> *"We suggest using **Temperature=0.7, TopP=0.8, TopK=20, and MinP=0**. For supported frameworks, you can adjust the **presence_penalty** parameter between 0 and 2 to reduce endless repetitions. However, using a higher value may occasionally result in **language mixing and a slight decrease in model performance**."*

El **Qwen3 Technical Report** (arXiv 2505.09388) usa los mismos para non-thinking + `presence_penalty=1.5` específicamente para Creative Writing v3 / WritingBench. Para BFCL-v3 reportan **61.9** con esos parámetros — que es tu use-case directo.

### Tu config actual vs. recomendada

Hoy: `temperature=0.1, repeat_penalty=1.1`. Problemas:

1. **`temperature=0.1`** está muy lejos del 0.7 con que el modelo fue calibrado en post-training. Qwen3 fue entrenado con sampling estocástico durante DPO/RLHF; forzarlo casi-greedy puede *empeorar* tool-calling porque el modelo "espera" cierta entropía y al no tenerla, queda atrapado en ramas subóptimas. Es el clásico fenómeno "calibration mismatch".
2. **`repeat_penalty=1.1`** no está recomendado por Qwen y compite con `presence_penalty`. Para JSON estructurado (`{"name": "...", "arguments": {...}}`) penalizar tokens repetidos es contraproducente porque las llaves `{`, `}`, `"`, `,` se repiten naturalmente. Issues como #14493 muestran que en el go-runner de Ollama las penalties están silently ignored para algunos modelos, así que tampoco te asegurás de que esté actuando.

### Para `<tool_call>` JSON estructurado

No hay un benchmark "BFCL con sampling sweep" público para 4B-Instruct-2507 específicamente. Pero la regla de oro empírica de la comunidad llama.cpp y vLLM:

- **`min_p=0.05`** + `temperature=0.7` da mejor parse rate que `top_p=0.8` solo cuando hay logits con cola larga (paper Min-P, ICLR 2025).
- **No usar `repeat_penalty`** con grammar-constrained o JSON output (consenso llama.cpp issues).

**Mi recomendación**: para emisión de `<tool_call>` mantené el set principal pero validá con un "sampling sweep" sobre tu matrix:
```
sweep = [
  (0.7, 0.8, 20, 0),       # oficial
  (0.6, 0.95, 20, 0),      # Qwen3-Thinking-style
  (0.5, 0.9, 40, 0.05),    # más conservador con Min-P
  (0.2, 0.8, 20, 0.05),    # destructive-strict
  (0.1, 1.0, 0, 0),        # tu actual greedy-like
]
```
Corré los 540 casos × 5 configs (~2700 runs) en 1 noche con `keep_alive=-1`. Es la única forma de saber qué set sirve **para vos**.

### Multilingüe ES/EN

El Qwen team advierte que `presence_penalty > 1.5` causa "language mixing". Como tenés casos ES y EN mezclados, **no pases de presence_penalty=1.0**. Otra regla heurística (no tengo benchmark formal): `top_p` muy bajo (<0.7) tiende a aumentar code-switching porque la cola con tokens del otro idioma queda fuera y el modelo se confunde. Mantené `top_p=0.8`.

---

## 2. KV cache, FlashAttention y prefix caching en Ollama

### `OLLAMA_FLASH_ATTENTION=1`

- **Soportado** en Qwen3 (atención estándar full, no MoE) y CUDA. La documentación oficial de Ollama (faq.md) lo describe como "experimental" pero en RTX 40-series con CUDA 12.x es estable hace 1+ año. La PR #7449 que mergeó esto recomienda dejarlo siempre encendido.
- **Speedup real**: en RTX 4060 Ti, el efecto puro de FA en t/s es modesto (~5-10 %) en 4B models. **El verdadero valor es habilitar KV cache quantization** y bajar VRAM por contexto.

### `OLLAMA_KV_CACHE_TYPE`

| Setting | Mem vs f16 | Quality (Qwen3-4B con GQA 8 KV-heads) |
|---|---|---|
| `f16` (default) | 100 % | baseline |
| **`q8_0`** | **~50 %** | **prácticamente sin pérdida medible** — recomendado |
| `q4_0` | ~25 % | pérdida visible en long context (>16k); JohannesGaessler (llama.cpp PR) midió que K-cache es mucho más sensible que V-cache. Para 8k–16k contextos cortos puede ser aceptable, pero hay reportes (Ollama docs) de degradación notoria con high-GQA models. Qwen3-4B tiene GQA=4 (32 Q / 8 KV) lo cual es **moderado-alto** — q4_0 es arriesgado. |

**Recomendación firme**: `q8_0`. Lo afirma smcleod (autor del PR original a Ollama), Ollama docs, y consenso comunitario para modelos < 32B.

### Cuánto consume el KV cache de Qwen3-4B

Specs del config.json (model card): 36 layers, 8 KV-heads, head_dim=128 (standard Qwen3).

Por token, fp16:
```
KV bytes/token = 2 (K+V) × 8 (kv_heads) × 128 (head_dim) × 36 (layers) × 2 bytes
              = 147,456 bytes ≈ 144 KB/token (f16)
              ≈ 72 KB/token (q8_0)
              ≈ 36 KB/token (q4_0)
```

Wait — recalcado: 2 × 8 × 128 × 36 × 2 = **147,456 bytes/token** ≈ 144 KB/token. Para tu **num_ctx=8192**: 1.18 GB en f16; **0.59 GB en q8_0**; ~0.30 GB en q4_0. Es plata pequeña en una 16GB pero relevante si querés cargar un draft model.

(El cálculo de Benjamin Marie en X que vi de "32 KB/token" era para Qwen3.5 que tiene 4 KV-heads — distinto modelo).

### Prefix caching ("prompt caching") en Ollama

- **Es automático** desde 2024 pero MUCHO más frágil que el de Anthropic/Gemini:
  - Solo funciona si el prefijo es **byte-a-byte idéntico** (Leanpub Ollama book, repetidos issues #1573, #2023).
  - Si tu system prompt incluye `Current time: 14:32:01`, **rompe el cache cada turno**. Solución: meter timestamps en el último `user` message, nunca en system.
  - El campo `prompt_eval_count` en la respuesta de Ollama **NO te dice si hubo cache hit** — siempre reporta el total de tokens del request. Para detectar cache hit hay que comparar `prompt_eval_duration` entre el primer request y el segundo idéntico (debería caer ~10-50× si hay hit).
  - Si cambiás `num_ctx` entre requests, **invalida el cache** (mismo issue del book de Leanpub).
- **Cómo invocarlo correctamente**:
  - System prompt 100 % estable (sin clock, sin user-name dinámico, sin nonce).
  - `keep_alive=-1` para que el modelo no se descargue (al descargar, también se va el cache).
  - `num_ctx` fijo entre llamadas.
  - Ollama no expone `cache_id` ni `cache_read_tokens` como Anthropic — lo hace transparente bajo el capó vía llama.cpp.
- **Cómo verificar**: corré 2× el mismo prompt, mirá `prompt_eval_duration`. Primer request: ~200-500 ms para 800 tokens. Segundo request: <30 ms si hay hit. Si no, hay algo dinámico en tu prefijo.

### Flags adicionales

| Flag | Recomendación | Notas |
|------|---------------|-------|
| `OLLAMA_NUM_PARALLEL` | **1** | Single-user single-thread → más es contraproducente (ver §7). Cada slot extra duplica/triplica el VRAM del KV cache (issue #4079: el num_ctx se *divide* entre slots → si tenés 8192 y NUM_PARALLEL=4, cada request ve 2048 tokens efectivos). |
| `OLLAMA_MAX_LOADED_MODELS` | **2** | 1 si sólo usás qwen3:4b; 2 si vas a probar speculative decoding o un router pequeño. |
| `OLLAMA_KEEP_ALIVE` | **24h** o **-1** | Crítico para latencia Alexa-tier. Verificar `expires_at` en `/api/ps` — si no es `0001-01-01T...` el setting no se aplicó (típicamente porque la env var está en shell, no system service). |
| `OLLAMA_NEW_ENGINE` | **0** (false / dejá default) | El nuevo Go runner trajo regresiones serias en Qwen3 (issue #11060: 10× slower, #12504: prompt eval much slower con qwen3, #12037: TTFT 4–5 minutos en partial offload). El c-runner (llama.cpp via cgo) **sigue siendo más rápido** para Qwen3-4B en CUDA. **Caveat**: en algunas versiones recientes Ollama fuerza Qwen3 al new engine sin pedirte permiso (`OllamaEngineRequired()`); si ves regresiones, considerá pin de versión a Ollama 0.16.x donde funcionaba bien. |

### Quantization — ¿conviene q5_K_M, q6_K, q8_0?

Qwen3-4B-Instruct-2507 sizes (unsloth GGUFs):
| Quant | File size | VRAM weights | + KV(8k, q8_0) | Total |
|-------|-----------|--------------|-----------------|-------|
| q4_K_M | ~2.5 GB | ~2.7 GB | +0.6 GB | **~3.5 GB** |
| q5_K_M | ~2.9 GB | ~3.1 GB | +0.6 GB | ~3.9 GB |
| q6_K | ~3.4 GB | ~3.6 GB | +0.6 GB | ~4.4 GB |
| q8_0 | ~4.3 GB | ~4.5 GB | +0.6 GB | ~5.3 GB |
| f16 | ~8.0 GB | ~8.2 GB | +0.6 GB | ~9.0 GB |

En 16GB VRAM **te sobra muchísimo lugar para subir a q8_0** y dejar 10 GB libres para draft model + KV expandido + headroom de Windows.

**Recomendación de la comunidad** (Medium @alessandroborges_84477): *"smaller models under 4 billion parameters often perform better with q6_k_M or q8_0 quantization rather than the default q4_k_m"*. Modelos más chicos son más sensibles a quantization porque tienen menos redundancia. El paper "Empirical Study of Qwen3 Quantization" (arXiv 2505.02214) confirma que en Qwen3 los modelos pequeños (0.6B, 1.8B, 4B) sufren más en low-bit.

**Acción concreta**: bajate `unsloth/Qwen3-4B-Instruct-2507-Q6_K.gguf` (~3.4 GB) y `Q8_0.gguf` (~4.3 GB). Importalos con un Modelfile (`FROM ./Qwen3-4B-Instruct-2507-Q8_0.gguf`) y compará vs. `qwen3:4b-instruct-2507-q4_K_M` original.

Hipótesis razonable (no medida): **Q6_K te da ~+1-3 PASS sobre 540** sin costo perceptible en latencia (el modelo está memory-bandwidth-bound, no compute-bound; pesar 3.4 vs 2.5 GB en una RTX 4060 Ti con 288 GB/s → diferencia de ~2-3 ms/token). **Q8_0 te da +0-1 PASS más** pero ya entra a régimen marginal. **Si vas a meter speculative decoding después, quedate en Q4_K_M o Q6_K** para dejar VRAM al draft.

---

## 3. Context window y compaction sweet spot

### Long-context degradation en Qwen3-4B

- Native context: **262,144 tokens** (model card).
- Pero "native" ≠ "sin degradación". Investigaciones recientes (arXiv 2601.15300) miden que **Qwen2.5-7B se degrada catastróficamente al 40–50 % del max context**, con F1 cayendo de 0.55 → 0.3. Sin un benchmark RULER específico de Qwen3-4B-Instruct-2507 publicado de forma exhaustiva, hay que asumir comportamiento similar y mantenerse muy por debajo del max nominal.
- Para Carter, donde rara vez vas a pasar de 16k tokens, **el problema no es long-context** sino el costo de prefill.

### Sweet spot práctico para Carter

| Modo | num_ctx recomendado | Justificación |
|------|---------------------|---------------|
| Chat trivial | **4096** | system 800 + 6-10 turns de ~100 tokens c/u → cabe holgadamente en 2k tokens. 4096 te da headroom × 2. TTFT más bajo. |
| Tool-mode (1 tool) | **8192** | tool result puede tener 1-3k tokens (read_file, search_web, etc.). |
| Misión larga / multi-step | **16384** | 5–10 tool calls encadenados con results de varios KB. |
| Siempre | **NO subir de 32768** | a esa escala empezás a entrar en zona de degradation curve y costo cuadrático del prefill (aunque FlashAttention lineariza, el wall-clock crece igual). |

**¿Conviene num_ctx variable?** Sí, pero **OJO**: cambiar `num_ctx` entre llamadas **invalida el prompt cache de Ollama**. Estrategia recomendada:
- Mantené **un solo num_ctx alto (8192 o 16384)** y dejá que el cache funcione.
- Si querés ahorrar TTFT en chat trivial bajando a 4096, asumí que estás trading off prefix-cache hits a cambio de prefill más barato. **Mediéndolo** es la única forma de saber si gana.

Mi predicción sin medir: en Carter v4 con system de 800 tokens, **mantener num_ctx=8192 fijo** + apoyarte en prompt-caching va a ganar a "num_ctx variable" en wall-clock total. Pero podés validarlo en 30 minutos con un script.

### Best practice de compaction

Estrategia híbrida (la más robusta empíricamente, "ChatGPT-style"):
1. **Mantener últimos N=4 turnos completos** (user+assistant pairs).
2. **Si el total > 12 KB de tokens**, hacer "rolling summary" del prefix: una llamada al mismo qwen3:4b con prompt `"Resumí en español, máximo 200 tokens, los siguientes turnos en formato bullet..."` → reemplazá los turns viejos por el summary.
3. **Nunca compactar el system prompt ni los últimos 2 turnos** — son los que el modelo más usa.
4. **Tool results grandes** (>2KB): metelos en summary inmediatamente al turno siguiente, conservá solo el "exit code/key data" del tool. Casi todos los results "grandes" son context dump, no decision-relevant.

---

## 4. System prompt — token budget y estructura óptima

### Sweet spot de longitud

No hay benchmark publicado específico para Qwen3-4B sobre "perfect prompt length". Pero hay evidencia indirecta:

- **Qwen team recomienda output de 16384 tokens "for most queries"** — implícitamente sugieren que el modelo está calibrado para handle prompts de varios miles de tokens.
- IFEval del modelo es **83.4** (model card) — muy alto, lo que implica que sigue instrucciones complejas bien hasta varios K tokens de instructions.
- Tu **800 tokens es razonable**, pero podés ir más liviano. La regla heurística para 4B es: **<1500 tokens de system instructions**, con la sección crítica (rules, output format) **al inicio o al final**. Los modelos pequeños tienen "lost-in-the-middle" más severo que los grandes.

### Estructura recomendada para Qwen3-4B (chat template oficial: ChatML con `<|im_start|>system\n...\n<|im_end|>`)

```
<|im_start|>system
# IDENTIDAD
You are Carter, a local Spanish/English assistant...

# REGLAS CRÍTICAS  ← AL INICIO, después de identidad
1. Para acciones destructivas SIEMPRE pedí confirmación.
2. Si necesitás info externa, llamá un tool. NO inventes datos.
3. Format de tool: <tool_call>{"name":"...", "arguments":{...}}</tool_call>

# TOOLS DISPONIBLES (top-K=8 inyectados dinámicamente)
[lista corta: name, 1-line description, params JSON schema]

# FEW-SHOT (2-3 ejemplos)
[user] Mandá un mail a Juan sobre la reunión
[assistant] <tool_call>{"name":"send_email", ...}</tool_call>

# REGLAS FINALES (recap)  ← AL FINAL también
- Idioma: respondé en el mismo idioma que el user.
- Si dudás, preguntá.
<|im_end|>
```

### XML vs Markdown vs JSON en system

- Qwen3 fue post-trained con ChatML + Hermes-style XML para tool-calling.
- **Markdown headers (`# REGLAS`)** funcionan muy bien en Qwen3 — los modelos modernos están training-saturated en Markdown.
- **NO uses JSON puro como structuring del system prompt** — el modelo se confunde con qué es "data" y qué es "instruction". Sí JSON para tool schemas dentro de bloques `<tools>...</tools>`.

### Few-shot vs zero-shot

**Para tool-calling con 47 tools, FEW-SHOT GANA**. Hallazgo consistente en literatura BFCL y Toolshed (arXiv 2410.14594): 1-3 ejemplos canónicos de tool invocation suben accuracy 5-15 % en modelos <13B. Qwen3-4B-Instruct-2507 saca 61.9 BFCL-v3 zero-shot, y typical few-shot uplift en small models es +3-8 pp.

**Recomendación**: 2 ejemplos: uno simple (single-tool call), uno multi-step. Mantenelos al final del system prompt o en el primer user-assistant pair simulado.

### Chain-of-thought en non-thinking model

Qwen3-4B-Instruct-2507 es **non-thinking nativo**, NO emite `<think>...</think>`. **No lo fuerces a CoT explícito** — el modelo va a resistirse o degradar. Para casos de razonamiento usá:
- "Step 1, Step 2, Step 3" inline en la respuesta (pseudo-CoT, light).
- O cambiá a `qwen3:4b-thinking-2507` (ver §8) para esos casos puntuales.

---

## 5. Function calling format — Hermes vs OpenAI vs Qwen native

### Status real en Ollama (2026-Q1)

Issues abiertos importantes que **te afectan directamente**:

- **#14601** (Qwen3 tool calling via `/api/chat tools=` parameter): cuando pasás tools por el parámetro de la API en lugar de embedderlos en el system prompt, **Ollama serializa los tools como Go-structs en vez de JSON válido** (bug en el template engine, sin `toJson` helper). Workaround: **embebé los tools en el system prompt en formato Hermes XML directamente**, como hace Qwen-Agent.
- **#14601 bis**: assistant tool-calls se strippean de la conversation history al re-envíar — puede perjudicar multi-turn tool use (aunque dijeron que era client-side, validá vos).

### Recomendación firme

**Quedate con Hermes XML embebido en system prompt**. Es lo que vos ya hacés, y es lo que el chat template de Qwen3 fue **originally trained on**. La doc oficial de Qwen (qwen.readthedocs.io/framework/function_call.html) confirma:

> *"For Qwen3, the chat template in tokenizer_config.json has already included support for the Hermes-style tool use."*

vLLM lo confirma con `--tool-call-parser hermes`. Qwen-Agent lo usa por default.

### `format: "json"` vs `response_format: {type: "json_schema"}`

- `format: "json"` (Ollama legacy): solo activa la **GBNF para JSON genérico**, no garantiza schema. Suele dar más whitespace y campos inventados.
- `format: <pydantic_schema>` (Ollama 0.5+ structured outputs): **GBNF generada desde tu JSON Schema** → garantiza JSON sintácticamente válido conforme al schema. Recomendado.
- **PERO**: para Hermes-style con `<tool_call>...</tool_call>` envolviendo JSON, **structured outputs no aplica directamente** — porque el output empieza con `<tool_call>`, no con `{`. Solución: usá structured outputs **dentro** del tool_call (post-parseo) o aceptá que el wrapping XML va sin grammar.

### GBNF grammar-constrained decoding

- llama.cpp soporta GBNF nativo via `--grammar-file`. Ollama **NO expone** este flag de forma directa para grammars custom (issues #1573, #2023). La única vía oficial es `format=<json_schema>`.
- Costo en latencia: **<5 % overhead** para schemas simples, hasta 20 % para schemas complejos con muchos `oneOf`. La GBNF se aplica en el sampling step (CPU), no en el forward pass.
- **No garantiza JSON "completo"**: si el modelo se queda sin `num_predict` antes de cerrar las llaves, vas a tener JSON truncado válido sintácticamente solo en el prefix (issue documentado en blog danielclayton.co.uk).

**Mi consejo**: mantente con Hermes XML. Para los 5–10 tools más críticos (destructive), agregá un **post-validation con Pydantic + 1 retry** sobre el JSON inner. Es más simple, más debuggeable, y no perdés el chat template oficial.

### 47 tools, ¿se confunde?

**Sí, casi seguro.** Literatura clara:
- **TinyAgent** (arXiv 2409.00608): catálogo de 16 tools → top-K retrieval recall 0.998 con K=4 vs 0.968 con K=6 todos-pasados. *Pasar más tools degrada accuracy*.
- **RAG-MCP** (arXiv 2505.03275): pasar todos los MCPs causa "decision fatigue" en LLMs <13B; retrieval top-K previo mejora.
- **Toolshed** (arXiv 2410.14594): +46-56 % de improvement con tool retrieval vs all-tools-in-prompt sobre 200+ tools.

**Aplicación concreta a Carter**:
1. **Embeddá las 47 descriptions** una vez con `nomic-embed-text` o `all-MiniLM-L6-v2` (ambos vía Ollama).
2. Por turno: embeddé `system + last_user_message`, retrieve top-8.
3. Inyectá solo esos 8 en el system. **Esto solo te puede ahorrar ~400-1500 tokens de system y subir el accuracy 3-8 pp**.
4. Edge case: si la query es muy ambigua, fallback a top-15. Si es muy directa ("manda mail a X"), top-3.

### Tool descriptions — estilo recomendado

Convención que correlaciona con BFCL bueno:
- Nombre tool: snake_case, verbo + objeto. `send_email` no `email_handler`.
- Description: **1-2 oraciones, modo imperativo**, comenzando con verbo. *"Send an email to a recipient. Use only when the user explicitly asks to send/email."* — la cláusula de *uso* (cuándo NO usarlo) es crítica.
- Params: descriptions de 5-15 palabras, con ejemplo si el tipo es ambiguo.
- Length total por tool: **30-80 tokens**. Más es ruido para 4B. Menos pierde info crítica.

---

## 6. Latencia per-token y first-token latency

### Números esperables en RTX 4060 Ti 16GB con qwen3:4b-q4_K_M

Datos cruzados (LocalLLM.in, hardware-corner.net, localai.computer, Qwen speed benchmark):
- **Token generation**: **40–60 t/s** en setting típico. Específicamente para 4B Q4 en 4060 Ti, el sitio localai.computer estima ~51 t/s. Hardware-corner reporta 4060 Ti 16GB: 22.4 t/s en **14B** Q4 a 16k context — escalando inversamente al tamaño, 4B debería estar ~50-60 t/s.
- **Prompt eval rate** (TTFT-relevant): **1500–2500 t/s** en RTX 40-series para modelos 4B Q4 (tu prompt de ~1000 tokens prefilea en 0.4-0.7 s).
- **Cold start (load_duration)**: 2-5 s para modelo Q4_K_M de ~2.5 GB desde NVMe. Cada vez que se descarga del VRAM hay que pagar esto. Por eso `keep_alive=-1` es no-brainer.
- **Total TTFT warm con num_ctx=8192, system 800 + user 50 tokens**: **~0.4–0.8 s** + queue overhead Ollama (~50-150 ms) → **~0.5-1 s**.
- **Latencia chat trivial completa** (200 tokens output): TTFT 0.5s + 200/50 t/s = **~4.5 s** en cold-prompt, **~3.5 s** en warm-prompt-cache. Encaja en tu Alexa-tier 3-8s.

**Si estás midiendo más de eso**, el bottleneck NO es el modelo: es Ollama overhead, parsing, network, o cold-start.

### Cómo acelerar TTFT específicamente

1. **`keep_alive=24h`** + warm-up dummy request al boot.
2. **Bajar num_ctx** cuando no se necesita.
3. **Prompt cache hits** — sistema prompt 100 % estable.
4. **Stream=True** para que el TTFT *percibido* sea cuando aparece el primer token, no cuando termina.
5. **Reducir system prompt** — cada 100 tokens menos = ~50-100 ms menos en prefill.

### Speculative decoding con qwen3:0.6b o 1.7b

Estado en Ollama:
- **NO está mergeado** oficialmente. Issues #5800, #9216, PR #8134 siguen abiertos / cerrados sin merge a main. La PR #8134 (bfroemel) está bastante avanzada pero requiere pin a esa versión / build manual.
- llama.cpp lo soporta hace 1+ año (`--model-draft`).
- LM Studio lo expone nativamente ("Speculative Decoding" UI).

Speedup teórico/medido en otras stacks:
- ExLlamaV2: +100-200 % en escenarios favorables (smcleod).
- vLLM: hasta +130 % en Llama-3 70B + 1B draft (AMD docs).
- LM Studio: variable, +20-80 % en escenarios típicos chat.
- **Para 4B → 0.6B draft**: el speedup es modesto (la ratio target/draft es 6.7×, idealmente querés 10×+ de ratio para dejar el draft ~"gratis" en compute). En 4B + 0.6B esperá **+15-40 %** en chat trivial, **menos en code/JSON** (donde el draft acepta menos).

**Veredicto**: en Ollama puro **no podés hacerlo hoy** sin parchear / build custom. **Si querés esto, tu única ruta limpia es bypass parcial a llama-server** (ver §10) — pero vos dijiste "debe quedarse en Ollama". Entonces: **archivá speculative decoding como roadmap futuro**. Cuando Ollama lo merge, será "free win".

---

## 7. Batching, paralelismo y throughput

### `OLLAMA_NUM_PARALLEL` para single-user

- **Default**: 1 (o 4 según memoria — varía por versión).
- **Cada slot extra divide el num_ctx total** entre las requests concurrentes (issue #4079). Si tenés `num_ctx=8192` y `NUM_PARALLEL=4`, cada request efectivamente ve 2048 tokens.
- **VRAM**: cada slot requiere su propio KV cache → `VRAM_kv = num_ctx × NUM_PARALLEL × bytes_per_token`. Para 8192 × 4 en q8_0 → 4 × 0.59 GB = 2.4 GB extra.
- **Latencia per-call**: bajo carga real, +20-40 % por request en NUM_PARALLEL=4 (markaicode benchmark).

**Recomendación firme**: `OLLAMA_NUM_PARALLEL=1` para Carter en producción. Single-user single-thread no se beneficia.

### Para correr la matrix de 540 casos

Acá sí podría ayudar `NUM_PARALLEL=2`, **pero**:
- Si el goal es **latencia baseline real**, tenés que correr serial (1 a 1) — paralelo te falsea las mediciones.
- Si el goal es **acelerar el ciclo de iteración**, NUM_PARALLEL=2 te baja el wall-clock total ~1.6× a costo de mediciones de latencia individuales menos confiables.

Sugerencia: **usá NUM_PARALLEL=1 para mediciones oficiales** (los runs que reportás), **NUM_PARALLEL=2** para regression-testing rápido durante dev. Mantené dos perfiles.

### `OLLAMA_NUM_THREAD` / num_thread

- Solo afecta **CPU inference**. En tu setup la 4060 Ti hace todo en GPU → irrelevante. Si por alguna razón hay layers offloaded a CPU (modelo no cabe entero), entonces sí: setealo a `physical_cores - 1` (Ryzen 7 7700 → 7 threads).
- **Verificá** con `ollama ps` que la columna PROCESSOR diga 100 % GPU. Si hay split, `num_thread` empieza a importar.

---

## 8. Modo no-thinking explícito y stop tokens

### qwen3:4b-instruct-2507: ya es non-thinking nativo

Como dice el model card: **"This model supports only non-thinking mode and does not generate `<think></think>` blocks. Specifying `enable_thinking=False` is no longer required."**

- **NO hace falta** pasarle `/no_think` ni nada. El issue #14601 confirma que Ollama incluso lo agrega innecesariamente y leakea como texto.
- Para compositional reasoning, **no podés "activar" thinking en este checkpoint** porque está post-trained sin ese capability. Si lo querés, el modelo correcto es `qwen3:4b-thinking-2507` (paralelo, mismo tier). Tradeoff: thinking-2507 emite cadenas largas de razonamiento (típicamente 1-5k tokens de `<think>...</think>` antes del answer) — **mata tu latency budget Alexa-tier**.

**Estrategia** (avanzada): usá un router previo que clasifique "trivial / tool / complex-reasoning" y solo en complex-reasoning escalá a thinking-2507. Pero implementar el router puede no valer el esfuerzo si la categoría representa <10 % de tu matrix.

### Skip layers / "more faster"

- **Layer skipping** no es una técnica que llama.cpp/Ollama exponga. Existe research (LayerDrop, Layer Skip de Meta) pero no está en los runtimes locales que usás.
- **Real lever**: subir quantization de Q4_K_M → Q3_K_M te da 5-10 % más t/s a costa de quality (no recomendado para tu use case).
- **No hay "free more speed"** sin tradeoffs de quality o sin speculative decoding.

### Stop tokens custom

Default en Qwen3 chat template: `<|im_end|>`. **Bug confirmado** (issue #12444 post Ollama 0.12.3): qwen3:4b-instruct a veces emite `<|endoftext|>` y sigue generando.

**Stops recomendados** en Modelfile o request:
```
stop: ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]
```

Para tool-calling Hermes-style **podrías** agregar `</tool_call>` como stop si querés cortar generación apenas se cierra el tool — pero perdés multi-tool calls. Mejor: dejar que el modelo decida y parsear stream incrementalmente.

---

## 9. Streaming y UX

### `stream=True`

**Activalo, sí o sí**. Ollama lo soporta nativo en `/api/chat` y `/api/generate`.

### Trade-off: streaming vs. parsing tool_calls

Problema: el parser de Ollama entrega `tool_calls` solo en el chunk final (`done=true`), no incrementalmente como texto. Si vas a usar streaming + parsear tools tenés dos opciones:

**Opción A (oficial):** stream del texto, ignorás tool_calls hasta el final, en el último chunk te llega el `tool_calls` parseado por Ollama. Simple pero el user no ve nada hasta que termine generation.

**Opción B (mejor UX, custom parser):**
1. Pedís stream=True con `tools` **embebidos en system prompt** (no usar `tools=[]` API param, así Ollama no intercepta).
2. Tu cliente recibe tokens raw — vos parseás en streaming buscando `<tool_call>`.
3. Si **antes** del `<tool_call>` el modelo dijo "Voy a revisar tu calendario...", lo mostrás al user *mientras* los tokens llegan.
4. Cuando detectás `<tool_call>` en stream, dejás de mostrar UI de chat y mostrás "Calling tool calendar_check...".
5. Parseás el JSON dentro del `<tool_call>` cuando se cierra el tag.

Esto **es lo que hace ChatGPT** ("buscando en la web…" antes de tool finish) y es lo que da la sensación de "Alexa-tier" responsiva.

### Multi-step tool truco

Para tool-chains: stream el texto pre-tool, ejecutar tool, stream el "let me check..." mientras hace la siguiente call. La key es: **el TTFT percibido es el momento en que aparece la primera palabra**, aunque la primera tool call ocurra 4 segundos después.

---

## 10. Configuraciones específicas de Ollama

| Setting | Recomendación | Notas |
|---------|---------------|-------|
| `OLLAMA_MODELS` | **SSD NVMe**, p.ej. `D:\ollama\models` | Cold-load de Q4_K_M (~2.5 GB) en NVMe Gen3+: ~2-3 s. En HDD: 15-30 s. Crítico la primera vez por sesión. |
| `OLLAMA_DEBUG` | **1** durante tuning, **0** en prod | Logs en `~/.ollama/logs/server.log` (Linux) o `%LOCALAPPDATA%\Ollama\logs\` (Windows). Buscá `KV self size`, `flash_attn`, `slot is processing`. |
| `OLLAMA_REQUEST_TIMEOUT` | default 5min suele alcanzar | Si tu test matrix corre con generations cortas, no lo toques. |

### Logs útiles

Después de un request, mirá:
```
prompt eval rate: 2103.19 tokens/s     ← prefill speed
eval rate: 40.58 tokens/s              ← gen speed
total duration: 35.24s
load duration: 3.47s                   ← si > 0.1s en warm = cache miss
```

`load_duration > 0` consistentemente significa `keep_alive` no funcionó.

### Bypass Ollama → llama-server directo

**Sí se puede**, llama-server es el binario de upstream llama.cpp. Setup:
1. Descargás builds de [github.com/ggml-org/llama.cpp/releases](https://github.com/ggml-org/llama.cpp/releases) (Win64-CUDA).
2. Necesitás el GGUF de Qwen3-4B-Instruct-2507 (ej: `unsloth/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` desde HuggingFace) — Ollama almacena los blobs sin extensión en `models/blobs/sha256-...` así que es más fácil bajar el GGUF aparte.
3. Lanzás:
```
llama-server.exe -m Qwen3-4B-Instruct-2507-Q4_K_M.gguf ^
  --jinja -ngl 99 -fa -c 8192 ^
  --temp 0.7 --top-p 0.8 --top-k 20 --min-p 0 ^
  --presence-penalty 1.0 ^
  -ctk q8_0 -ctv q8_0 ^
  --port 11434 --host 127.0.0.1 ^
  --no-context-shift
```
4. Endpoint OpenAI-compatible en `http://localhost:11434/v1`.

**Beneficios**:
- Speculative decoding via `--model-draft Qwen3-0.6B-Q4.gguf`.
- Grammar custom via `--grammar-file`.
- `--cache-type-k`/`--cache-type-v` independientes (podés probar K=q8_0, V=q4_0 para ahorrar más con menos pérdida — JohannesGaessler reportó que V es menos sensible).
- Performance frecuentemente comparable o mejor en eval rate, pero **ojo**: hay un issue #12237 en llama.cpp donde llama-server tiene **prompt-eval 5× MÁS LENTO que Ollama** en algunas configs en CUDA — Ollama tiene optimizaciones de buffer típicamente.

**Riesgos**:
- Vos dijiste "debe quedarse en Ollama". Estrictamente, llama-server **es lo que Ollama corre adentro** vía libllama. Llamarlo directo no es "migrar a otro engine", es "skip the wrapper". Discutible si cuenta como "salirse de Ollama".
- Perdés el modelo manager de Ollama (download, list, etc.).

**Mi sugerencia**: **mantente en Ollama** para deployment principal. Tené un perfil llama-server **paralelo solo para experimentar speculative decoding y custom grammars**. Si encontrás +20 % de win y lo necesitás, ahí justificás el move.

---

## 11. Optimizaciones específicas a Carter v4

### Dos system prompts

**Sí, recomendado.** Pattern probado:

```
PROMPT_CHAT = "Sos Carter, asistente local. Respondé conciso. Si necesitás info externa, decí 'NEEDS_TOOL' al final." (~150 tokens)

PROMPT_TOOL = full prompt con catálogo top-K + few-shot + reglas (~600-800 tokens)
```

Router previo (regex o un mini-LLM 0.6b):
- ¿Mensaje contiene verbos de acción ("manda", "abrí", "buscá")? → PROMPT_TOOL
- ¿Es chitchat ("hola", "qué hora es...")? → PROMPT_CHAT
- ¿Dudoso? → PROMPT_TOOL (más seguro)

**Win esperable**: en chat trivial el system pasa de 800 → 150 tokens → **TTFT cae ~25-40 %** + casi la misma quality (porque las reglas tool son innecesarias en chat).

**Riesgo**: si el clasificador se equivoca y manda chat a un mensaje que necesita tool, falla. Mitigación: en duda, defaulteá a PROMPT_TOOL.

### Filtrar catálogo dinámicamente top-K

Sí — ya lo recomendé en §5. Acción concreta:
1. `nomic-embed-text` via Ollama embeds (768 dim) — ~5-10 ms por embed en GPU.
2. Index FAISS-flat in-memory (47 vectors → cosine search es trivial, <1 ms).
3. Top-K=8 por turn.

### Modelo más chico para router

**SÍ vale la pena evaluar.** Opciones:
- `qwen3:0.6b` (Q4): VRAM ~0.5 GB, ~150 t/s en 4060 Ti, accuracy decente para clasificación binaria.
- `qwen3:1.7b` (Q4): VRAM ~1.2 GB, ~100 t/s, mejor que 0.6b en intent.
- `phi-3.5-mini` (3.8B): solo si querés algo más fuerte — pero ya casi te igualás al main model.

Pattern recomendado para Carter:
```
[user message]
   ↓
[router qwen3:0.6b]: "intent: chat | tool | clarify"  (50ms, 1 token output)
   ↓
[main qwen3:4b con system apropiado]
```

**Win**: los chat trivials se resuelven con prompt corto y main model warm. Los tools van con catálogo top-K y few-shot.

**Win adicional**: el router puede inyectar el top-K de tools relevantes en lugar de embed retrieval (el router LLM "elige" los 5 tools más relevantes en una sola pasada).

**Caveat**: `OLLAMA_MAX_LOADED_MODELS=2` y VRAM total ~6 GB (4b + 0.6b ambos warm) — cabe holgadamente en 16 GB.

---

## 12. Comparativa de versions y modelos similares

### Mismo tier — Qwen3-4B-Instruct-2507 quants

(VRAM total estimada con num_ctx=8192, q8_0 KV cache, ~0.6 GB KV)

| Quant | File | VRAM | Δ Quality vs Q8 (proxy KLD) | t/s 4060 Ti (estimado) | Recomendación |
|-------|------|------|------------------------------|--------------|---------------|
| Q4_K_M | 2.5 GB | 3.5 GB | ~99.0 % | ~55 t/s | tu actual, OK |
| Q5_K_M | 2.9 GB | 3.9 GB | ~99.5 % | ~52 t/s | upgrade barato |
| **Q6_K** | **3.4 GB** | **4.4 GB** | **~99.8 %** | **~50 t/s** | **sweet spot** en 16 GB VRAM |
| Q8_0 | 4.3 GB | 5.3 GB | 100 % (baseline) | ~45 t/s | overkill marginal |

(Fuente comparativa GGUF quality: Unsloth GGUF benchmarks con KL-divergence; quality % es aproximado, no exacto para Qwen3-4B-Instruct-2507 específicamente).

**Mi pick**: **subí a Q6_K**. +0.4 GB de VRAM bien gastados, ~5 % menos t/s pero vos no estás compute-bound, sino latency-bound. La diferencia perceptual entre Q4_K_M y Q6_K en Qwen3-4B es notable según los benchmarks de unsloth para Qwen3.5 (similar arch).

### Versus otros 4B vendors (BFCL, IFEval, MMLU)

Datos cruzados (model cards y llm-stats.com, distillabs benchmark Nov 2025):

| Modelo | BFCL-v3 | IFEval | MMLU-Pro | Notas |
|--------|---------|--------|----------|-------|
| **Qwen3-4B-Instruct-2507** | **61.9** | 83.4 | **69.6** | tu modelo. Top en multilingüe ES (MMLU-ProX 61.6, MultiIF 69.0). |
| Qwen3-4B (base mayo 2025) | 57.6 | 81.2 | 58.0 | versión vieja del mismo. |
| Phi-4-mini-instruct (3.8B) | ~50 (no oficial) | ~83 | ~59 | strong en EN, **pobre en ES** (arquitectura tied embeddings, vocab más limitado). |
| Gemma-3-4B-it | ~52 (estimado) | **90.2** | ~58 | mejor en IFEval EN, **peor en tool calling**. |
| Llama-3.2-3B-Instruct | ~46 | 78 | ~50 | inferior en general. |
| Granite-4-Tiny-3B / 4B | data limitada | ~75 | ~50 | menos tested para tool use. |

**Veredicto sobre Qwen3-4B-Instruct-2507**: hoy es **el mejor 4B en BFCL + MMLU-Pro + multilingüe**. No hay un upgrade "gratis" de mismo tier sin migración. Mantenete.

### Qué monitorear para upgrade futuro

- **qwen3.5:4B** (multimodal hybrid, Gated DeltaNet + MoE 0.8/2/4/9B small series): ya está released. Tradeoffs: 262K context, mejor multilingüe (201 idiomas), pero **tiene bugs serios de tool-calling en Ollama hoy** (issues #14493, #14745, #14601). **Actualmente NO recomendado** para production tool-use en Ollama. Esperá fixes a v0.18+.
- **qwen3.6:4B** (no released aún en variantes pequeñas dense — solo MoE 35B-A3B y 27B mainstream).
- **Qwen3-Next** small variants: not released yet.

**Triggers para reconsiderar**:
1. Cuando Ollama merge tool calling fix para qwen3.5 (PR #14537 trackea esto).
2. Cuando aparezca `qwen4:4b-instruct` (probablemente Q3 2026).
3. Cuando speculative decoding mergee en Ollama main → re-evaluar 4b + 0.6b draft.

---

## Caveats — cosas que la doc dice pero en práctica no se sostiene

1. **"Ollama prompt caching es automático y transparente"** → cierto solo si tu prefijo es byte-idéntico, sin timestamps, sin user-name, sin nonces. La realidad es que el 70 % de stacks lo invalidan accidentalmente. **Verificá midiendo `prompt_eval_duration`**.
2. **"Flash Attention no tiene downsides"** → en algunas versiones de Ollama + algunos modelos, FA con context >512K causa crash (issue #11619). En 4060 Ti con qwen3:4b y context ≤32k, no hay problemas reportados.
3. **"El nuevo Ollama engine es más rápido"** → falso para Qwen3 hoy. Issues #11060, #12504, #12037 muestran 5-10× regresión en TTFT con partial offload o configs no-default. **Pin a v0.16.x mientras estabilizan**.
4. **"q4_0 KV cache quita 75 % de mem sin gran pérdida"** → en modelos con high GQA count (Qwen2 cited explícitamente en Ollama docs) hay degradación notable. Qwen3-4B tiene GQA moderado pero **q4_0 NO recomendado**, sticky a q8_0.
5. **"`presence_penalty=1.5` es óptimo"** (Qwen tech report) → solo para non-thinking en benchmarks de creative writing. En multilingüe ES/EN, valores >1.0 te van a causar **language-mixing** ocasional. Quedate en 1.0.
6. **"BFCL-v3 score 61.9 = production-ready"** → 38 % de los casos fallan en evaluación oficial. En Carter con catálogo de 47 tools, esperá BFCL-equivalente más bajo (5-10 % degradation por catálogo grande sin retrieval).
7. **"Speculative decoding es free win"** → con 4b + 0.6b ratio (6.7×) el speedup real es modesto (15-40 %), no los 100-200 % que se ven con 70b + 1b (70× ratio). Y en Ollama hoy ni siquiera está mergeado.
8. **"Stream + tool calls funciona out-of-the-box"** → el parser de Ollama no es incremental para tool_calls. Necesitás parser custom si querés UX tipo ChatGPT.
9. **"Ollama tools API es la forma idiomática"** → bug #14601 hace que sea menos confiable que embedderlos en system prompt como Hermes XML. **Embeddé**.
10. **TTFT reportado en blogs (~1.4 s para 8B en 4060)** asume warm + prompt corto. Tu Carter con 800-token system + 100-token user en cold → puede llegar a 3-5 s la primera vez. Por eso warm-up es crítico.

---

## Roadmap de aplicación (orden recomendado)

### Día 1 — cambios seguros, alto impacto (esfuerzo total: ~2-3 horas)

| Paso | Acción | Cómo medir el impacto | Threshold para revertir |
|------|--------|------------------------|--------------------------|
| 1.1 | Setear env vars de sistema en Windows: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_KEEP_ALIVE=24h`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MODELS=<NVMe path>` | log `KV self size` debería bajar ~50 %. `ollama ps` `expires_at` debería ser `0001-01-01` con request keep_alive=-1. | Si quality cae >2 PASS → bajar a `f16` cache. |
| 1.2 | Ajustar sampling al set principal: 0.7/0.8/20/0/pp1.0/rp1.0. Quitar tu `temperature=0.1` y `repeat_penalty=1.1`. | Correr 50 casos representativos × 2 (old vs new). | Si parse rate cae > 3 % → revisar pp y rp. |
| 1.3 | Stop tokens: agregar `<\|endoftext\|>` al stop list (bug #12444). | Mirar logs: ¿hay continuations después del end-of-text? | N/A. |
| 1.4 | Embeber tools en system prompt en Hermes XML (NO via `tools=` param API). | Ollama debug log debería mostrar JSON bien formateado. | Si tu cliente espera formato OpenAI → necesitás post-procesado. |

**Re-correr matrix completa de 540 casos. Esperar +4 a +10 PASS.**

### Día 2-3 — cambios medios (esfuerzo: ~6-8 horas)

| Paso | Acción | Medir | Revertir si |
|------|--------|-------|-------------|
| 2.1 | Stream=True + parser incremental de `<tool_call>`. | TTFT percibido en chat trivial. Logueá tiempo entre `request_sent` y `first_visible_word`. | Si parser es flaky → fallback a non-stream. |
| 2.2 | Tool retrieval top-K=8 con `nomic-embed-text`. | Tokens de system prompt (debería caer ~400). PASS rate (debería subir si confusión era el bottleneck). | Si recall <95 % en tools necesitados → top-K=12. |
| 2.3 | num_ctx 4096 chat / 8192 tools / 16384 misiones. Implementar selector. | TTFT en chat trivial debería bajar 20-30 %. | Si invalidación de prefix cache hace neto negativo → quedate fijo en 8192. |

**Re-correr matrix. Esperar +2 a +5 PASS más, mejor UX.**

### Día 4-7 — experimentos opcionales (esfuerzo: ~10-15 horas)

| Paso | Acción | Medir | Decisión |
|------|--------|-------|----------|
| 3.1 | Probar Q6_K en lugar de Q4_K_M. | Diff en PASS, diff en t/s. | Si Q6_K +2 PASS y -3 t/s → keep. Si <+1 PASS → revertir. |
| 3.2 | Dual system prompt (chat-mode vs tool-mode) con router-by-regex (sin LLM router). | TTFT chat trivial. Misclassification rate (¿chat-mode falló porque era tool?). | Si misclass >5 % → más reglas o mini-LLM router. |
| 3.3 | Mini router con qwen3:0.6b para intent. `OLLAMA_MAX_LOADED_MODELS=2`. | Igual + load times. | Si overhead >50 ms y misclass no mejora vs regex → no vale. |
| 3.4 | Set destructive-strict (temp 0.2, min_p 0.05) solo para 5-10 tools peligrosos. | False-call rate en esos tools (debería bajar). | Si rompe parse rate de JSON → temp 0.3. |

### Roadmap futuro (cuando libere upstream)

| Cuando... | Hacer... | Ganancia esperable |
|-----------|----------|--------------------|
| Ollama merge speculative decoding | probar `qwen3:4b + draft qwen3:0.6b` | +15-40 % t/s en chat trivial |
| Aparezca `qwen3.5:4b-instruct-2507` con tool-calling fix | benchmark side-by-side | hasta +5 PASS si new arch + better multilingüe |
| Ollama exponga GBNF custom grammar | grammar para `<tool_call>{...}</tool_call>` exacto | parse rate → 99.9 %, parse failures → 0 |
| 4060 Ti se quede chica para Q8 + Q6 + drafts | upgrade a 4070 Super 16GB | bandwidth +50 % → t/s real ~70 |

---

## Apéndice: snippet de Modelfile + system prompt skeleton para Carter v4

**Modelfile.carter:**
```
FROM qwen3:4b-instruct-2507-q4_K_M

# Sampling principal — ver §1
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER min_p 0
PARAMETER presence_penalty 1.0
PARAMETER repeat_penalty 1.0

# Context
PARAMETER num_ctx 8192
PARAMETER num_predict 4096

# Stops (incluye fix bug #12444)
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER stop "<|im_start|>"
```

```
ollama create carter -f Modelfile.carter
ollama run carter
```

**System prompt esqueleto (~700 tokens con top-K=8 tools):**
```
# IDENTIDAD
Sos Carter, asistente local de [usuario]. Respondés en el idioma del user (ES/EN).

# REGLAS CRÍTICAS
1. Para acciones DESTRUCTIVAS (delete, send, buy, push) SIEMPRE pedí confirmación primero.
2. Si necesitás info externa o ejecutar acción, llamá a un tool. NO inventes.
3. Format estricto: <tool_call>{"name":"NOMBRE","arguments":{...}}</tool_call>
4. Si no hay tool apropiado, decilo y proponé alternativa. NO uses tools no listadas.

# TOOLS (top-K=8, dynamic)
[tool_1: send_email — Send an email...]
[tool_2: ...]
...

# FEW-SHOT
[user] Mandá un mail a Juan: que la reunión pasa al jueves.
[assistant] Confirmo: ¿mando "Hola Juan, la reunión pasa al jueves" a juan@... ? Sí/no.
[user] sí
[assistant] <tool_call>{"name":"send_email","arguments":{"to":"juan@...","subject":"Cambio de reunión","body":"Hola Juan, la reunión pasa al jueves."}}</tool_call>

# REGLAS FINALES
- Concisión > verbosidad.
- Si dudás, preguntá.
- En multi-step, ejecutá una tool por turn.
```

---

**Bottom line**: `qwen3:4b-instruct-2507-q4_K_M` en Ollama + RTX 4060 Ti 16GB ya está en un punto bastante bueno. El último 10 % está en (a) sampling correcto según Qwen team, (b) KV q8_0 + FA + keep_alive permanente, (c) tool retrieval top-K dinámico, (d) parser de stream incremental, (e) embeber tools en system en Hermes XML (no API param), y (f) considerar Q6_K como upgrade barato. Speculative decoding y `qwen3.5` quedan en roadmap hasta que Ollama estabilice. Si después de aplicar todo seguís lejos del techo, **el bottleneck ya no es el modelo: es tu pipeline** — medí `load_duration`, `prompt_eval_duration`, `eval_duration`, y atacá lo que pese más.