# Carter v4 — Arquitectura Dual-LLM vs Single-Model por perfil de hardware (Ollama 0.20.4+, mayo 2026)

## TL;DR

- **Dual-LLM no compensa en ningún perfil ≤10 GB y solo gana marginalmente en 12/16 GB.** En perfiles 0/6/8/10 GB la respuesta es inequívoca: un único `qwen3:4b-instruct-2507-q4_K_M` (o más pequeño) gana en accuracy real, simplicidad y latencia. En 12/16 GB la mejor jugada NO es dual sino subir el modelo único a `granite4.1:8b` (BFCL 68.27) o quedarse con Qwen3-4B y añadir headroom para verifier/embeddings. Solo en **24 GB** la arquitectura dual o un modelo único de mayor tamaño (`gpt-oss:20b`, `granite4.1:30b`, `qwen3:30b-a3b-thinking-2507`) abre ventaja de >10% accuracy.
- **El bottleneck del Carter actual NO es el modelo — es Ollama.** Tres bugs vigentes en mayo 2026 condicionan toda la decisión: (1) `qwen3:4b-thinking` sigue rompiendo cuando se combina `think=true + tools` (issue #10976 abierto desde junio 2025), (2) el parser Qwen3 devuelve HTTP 500 al truncar tool calls largos (#14570) y omite la última call en multi-tool (#11232), (3) requests a modelos distintos cargados en VRAM **se serializan en un único `ollama serve`** con head-of-line blocking de hasta 50 s (#14578). Esto convierte el "switch warm" entre chat y tools en una falacia operacional bajo un solo daemon.
- **Speculative decoding NO está disponible en Ollama para Linux/Windows en mayo 2026.** El PR #8134 sigue sin mergear, el #9216 sigue abierto, y la única release que lo soporta es **0.23.x SOLO para Gemma 4 MTP en Macs (MLX)**. En Windows con Carter no es opción hoy. Si quieres speculative decoding tienes que salir de Ollama (llama.cpp directo, vLLM, o LM Studio) — lo cual rompe el supuesto Ollama 0.20.4+ obligatorio. Conclusión: planifica como si no existiera.

---

## 1. Tabla maestra por perfil VRAM (secciones 2 + 7 + 8A unificadas)

VRAM "usable" = 80% del nominal (deja ~20% para Windows compositor, KV cache headroom, otros procesos). Tamaños GGUF Q4_K_M con KV cache q8_0 (Ollama default ya en flash-attention). Estimaciones TTFT en hardware mid-range (RTX 3060/4060 clase) basadas en benchmarks Hardware Corner / Database Mart / Inferencerig 2026.

| Perfil | VRAM usable | **Recomendación final** | Modelo CHAT | Modelo TOOLS | Router | VRAM total | TTFT chat | TTFT tool | BFCL-v3 esperado | ¿Mejora vs `qwen3:4b` solo? |
|---|---|---|---|---|---|---|---|---|---|---|
| `cpu_fallback` (0 GB) | 0 GB GPU / RAM | **SINGLE** `qwen3:1.7b-instruct` Q4_K_M | mismo | mismo | regex | 1.4 GB RAM + 0.4 KV | 1.5–3 s | 4–8 s | ~50% | n/a (4B no entra en CPU razonable) |
| `low_vram_6gb` | 4.8 GB | **SINGLE** `qwen3:4b-instruct-2507-q4_K_M` (status quo) | mismo | mismo | regex | 2.5 + 1.0 KV ≈ 3.5 GB | 250–400 ms | 700 ms–1.5 s | ~62% (validado 90% en Carter 18×30) | NO migrar |
| `balanced_8gb` | 6.4 GB | **SINGLE** `qwen3:4b-instruct-2507-q6_K` (subir cuant) o `granite4.1:3b-instruct` Q5 | mismo | mismo | regex | 3.2 + 1.5 KV ≈ 4.7 GB | 200–350 ms | 600 ms–1.2 s | ~63% | Marginal (+1–3% accuracy con Q6_K) |
| `balanced_10gb` | 8 GB | **SINGLE** `granite4.1:8b-instruct` Q4_K_M | mismo | mismo | regex | 5.3 + 1.8 KV ≈ 7.1 GB | 350–500 ms | 1.0–1.8 s | **68.27%** (oficial IBM/BFCL-v3) | **+6 pts BFCL** vs qwen3:4b — migrar |
| `high_quality_12gb` | 9.6 GB | **SINGLE** `granite4.1:8b-instruct` Q5_K_M ó `qwen3:8b-instruct` Q5 | mismo | mismo | regex | 6.5 + 2.5 KV ≈ 9.0 GB | 350–500 ms | 1.0–1.8 s | 68–70% | +6–8 pts BFCL — migrar |
| `high_quality_16gb` | 12.8 GB | **DUAL viable pero NO óptimo**: `granite4.1:8b` Q4 + `qwen3:0.6b` (router/draft) ≈ 6.8 GB; **mejor: SINGLE `granite4.1:8b` Q6_K + verifier headroom** | granite4.1:8b Q6 | mismo | regex | 8.0 + 3 KV ≈ 11 GB | 300–450 ms | 0.9–1.6 s | ~70% | +8 pts BFCL — migrar |
| `top_tier_24gb` | 19 GB | **DUAL gana aquí**: `qwen3:4b-instruct-2507` (chat fluido ES/EN) + `granite4.1:30b-instruct` Q4 (tools élite) | qwen3:4b Q4 (2.5 GB) | granite4.1:30b Q4 (~18 GB) | regex | ~21 GB | 200–350 ms | 2–3.5 s | **73.68%** (BFCL líder open) | **+11.7 pts BFCL** — migrar dual |

**Notas críticas:**

- En `cpu_fallback` `qwen3:4b` Q4_K_M corre en CPU pero a ~3–6 tok/s — TTFT chat real será 2–4 s y tool requests 8–15 s. Por debajo del target <500 ms / <2 s. **`qwen3:1.7b` es honesto** porque admite que la experiencia será degradada; `llama3.2:3b` se descartó por debilidad en español documentada (Ollama Cheat Sheet 2026, model card).
- En 6 GB **DUAL es físicamente posible** con `qwen3:0.6b` (0.5 GB) + `qwen3:4b-instruct-2507` (2.5 GB) + KV cache (~1 GB) = 4 GB; cabría. Pero `qwen3:0.6b` NO tiene BFCL competitivo (solo serviría como router, no como chat fluido), y duplicar inferencia mata la latencia chat trivial. La experiencia nunca supera al single de 4B.
- En 24 GB también se estudió `gpt-oss:20b` (~12 GB MXFP4) como single — TauBench fuerte pero **bugs de tool calling con harmonyparser persisten** (issues #11991, HF discussion #80) y el modelo prefiere texto narrativo con `commentary to=functions...` que ollama parsea inconsistentemente. **No recomendado para production tool-calling en mayo 2026** salvo que se use Cline con XML tool format manual.
- **`xLAM-2-8b-fc-r` queda fuera oficialmente**: el modelo solo carga tools correctamente con vLLM + plugin parser custom (`xlam_tool_call_parser.py`); en Ollama vía `/api/generate` retorna None/empty (issue documentado en CrewAI community). No registra tools en Ollama 0.20.4+.
- **`watt-tool-8B`** está disponible (`hengwen/watt-tool-8B`) pero usa template Llama-3.1 estándar — funciona en Ollama, pero su SOTA en BFCL es de inicios 2025; en mayo 2026 lo supera `granite4.1:8b` (68.27 vs ~70 watt-tool, sin métricas oficiales recientes). No vale el cambio.

---

## 2. Análisis de routing (sección 4) por estrategia × perfil

| Estrategia | Latencia chat trivial | Latencia tool req | Accuracy routing | Overhead complejidad | Riesgo inconsistencia | Perfiles donde aplica |
|---|---|---|---|---|---|---|
| **A. Regex/heurística estructural** | 0 ms | 0 ms | 90–95% (depende de qué señales: imperativos, verbos de acción, mention de archivos/ventanas) | Bajo (~150 LOC Python) | Bajo: el modelo TOOLS recibe la consulta original aunque el regex falle | **TODOS los perfiles, incluido cpu_fallback** |
| **B. Router LLM mini (qwen3:0.6b)** | +50–80 ms (decisión router) | +50–80 ms | >97% (qwen3:0.6b en clasificación binaria intent | tool) | Alto: 3 modelos cargados, coordinación, prompt engineering del router | Medio: el router puede alucinar sobre tools no disponibles | **Solo ≥10 GB** (necesita 0.5 + chat + tools en VRAM) |
| **C. Sin router (chat decide tool_calls)** | igual al modelo único | igual al modelo único | 95%+ con qwen3:4b-instruct-2507 (validado en Carter 90%) | Mínimo | Cero (un solo modelo) | **TODOS** — es el status quo de Carter |
| **D. Cascading (chat siempre primero, tools en paralelo si detecta intent)** | TTFT chat lo más rápido (200–400 ms) | TTFT tool +400–600 ms (porque chat ya gastó budget) | 92% (race condition: chat puede empezar a responder y luego invalidar) | Muy alto | **ALTO**: chat dice "voy a buscar" y tools no llama → exactamente el escenario de mentira que Carter prohíbe por construcción | No recomendado |

**Recomendación universal: Estrategia A (regex)** para todos los perfiles. Justificación:

1. **Cumple "honestidad por construcción"**: el verifier estructural (frame-diff numpy + Win32 API) ya valida ex-post. Un router LLM añadiría una capa de hipotetización entre user input y tool execution que es exactamente lo que Carter quiere evitar.
2. **Es agnóstico al hardware**: funciona en cpu_fallback igual que en 24 GB.
3. **Accuracy de 90–95% es suficiente** porque el fallback siempre es "pasar la consulta original al modelo CHAT/TOOLS único" — un falso negativo del router no produce mentira, produce una llamada al tool model que generará respuesta texto en vez de tool_call (el verifier lo detecta).
4. La estrategia B parece atractiva en 16/24 GB pero el trade-off latencia (50–80 ms × 2 si hay handoff) anula el beneficio de tener "el modelo correcto" cuando regex acierta el 95% del tiempo.

**Patrón regex recomendado para Carter:**
- Verbos de acción Win32: `abrir|cerrar|maximizar|minimizar|cambiar|enfocar|buscar archivos|ejecutar|capturar|hacer click`.
- Imperativos en ES/EN: `^(open|close|run|launch|abre|cierra|ejecuta|busca|haz)\b`.
- Mention de paths o extensiones: `\.[a-z]{2,4}\b|C:\\|/home/|~/`.
- Match → ruta TOOLS. No match → ruta CHAT (o single-model si aplica).

---

## 3. Realidad operacional Ollama dual-model (sección 6) en mayo 2026

### 3.1 Bugs críticos vigentes

| Issue | Estado mayo 2026 | Impacto Carter |
|---|---|---|
| **#10976** "Thinking + tools + qwen3 = empty output" | **ABIERTO desde junio 2025**, sin fix | `qwen3:4b-thinking-2507` (BFCL 71.2) **inutilizable** para tools en Ollama. Bloquea la opción "thinking model como TOOLS specialist". |
| **#11232** "Parser generates incorrect tool calls compared to Qwen3 model output" | Abierto, multi-tool calls truncados | Carter no puede confiar en Qwen3 para parallel tool calls; debe encadenar serializadamente (lo que ya hace ReAct con max 3 cadenas). |
| **#14570** "qwen3 tool call parser returns 500 when truncated" | Abierto, requiere `num_predict=-1` workaround | Tool calls con argumentos largos (ej: filesystem_write con contenido) crashean. **Hay que setear `num_predict=-1` o `num_ctx` generoso**. |
| **#12917** "qwen3:4b: Can't turn off thinking" | Cerrado parcialmente, persiste en algunas builds | `/no_think` no siempre se respeta — usar `qwen3:4b-instruct-2507` (no thinking variant) explícitamente. |
| **#14578** "Requests to different loaded models serialize ~50s" | **ABIERTO**, Apple Silicon confirmado, Linux/Windows probable | **Si Carter carga 2 modelos en mismo `ollama serve`, requests se serializan globalmente.** Es el killer-bug del enfoque dual. Workaround: 2 instancias `ollama serve` en puertos distintos (11434 + 11435). |
| **#9926 / #5272** "keep_alive eviction loop" | Cerrado pero recurrente, override por API persiste | Cliente que envía `keep_alive: "5m"` por defecto sobrescribe `OLLAMA_KEEP_ALIVE=-1`. Carter debe enviar **explícitamente `keep_alive: -1`** en todas las llamadas a ambos modelos. |
| **#11196** "Multiple instances of same model" | Abierto | No relevante para dual diferentes. |

### 3.2 Comportamiento empírico

- **OLLAMA_MAX_LOADED_MODELS=2 o 3 funciona estable** en 0.20.4+ siempre que VRAM físicamente lo aguante (Ollama estima requirements y no carga si excede). En Windows + ROCm hubo limitaciones históricas con Radeon (default 1) — en NVIDIA no aplica.
- **Switch warm entre modelos cargados: ~50–200 ms** si ambos están en VRAM (solo cambia el contexto de inferencia activo). Si uno está evicted: 3–10 s cold start.
- **Inferencia simultánea en 2 modelos cargados: SE SERIALIZA** dentro del mismo `ollama serve` (issue #14578 confirmado). Esto es el dato más importante de toda esta investigación: el dual no paraleliza tu chat trivial mientras tools genera. El head-of-line blocking puede llegar a 50 s en casos extremos.
- **Workaround production-grade**: dos daemons `ollama serve` en `127.0.0.1:11434` (chat) y `127.0.0.1:11435` (tools) con `OLLAMA_MODELS` y `CUDA_VISIBLE_DEVICES` apropiados. **Esto rompe el supuesto "127.0.0.1:11434 único"** del proyecto Carter.
- **`keep_alive=-1` en ambos**: no genera eviction loop si VRAM cabe — Ollama simplemente rechaza cargar el segundo si no cabe (no evict el pinned). El "eviction loop" reportado en variantes del bug es por clientes que sobrescriben con `5m`.

### 3.3 Implicación para Carter

> Si decides ir dual, **exige correr 2 `ollama serve`**. Eso significa cambiar el supuesto del proyecto. Si mantienes un único daemon, dual con MAX_LOADED_MODELS=2 funcionará para casos burst-friendly pero serializará bajo concurrencia, anulando la ganancia de latencia que era la razón de hacer dual en primer lugar.

---

## 4. Decisión final por perfil (sección 8 expandida)

### Trigger de migración (recordatorio del usuario)
- Si ganancia <10% velocidad y <5% accuracy → **single-model**.
- Si gana >20% velocidad O >10% accuracy → **migrar**.
- Tool accuracy pesa más que velocidad.

### 4.1 Perfil `cpu_fallback` (0 GB GPU)

- **Recomendado**: `qwen3:1.7b-instruct` Q4_K_M (1.4 GB RAM, ~3–6 tok/s en CPU moderna).
- **Vs status quo (qwen3:4b en CPU)**: qwen3:4b corre pero a 1–3 tok/s, TTFT chat 2–5 s, tool req 8–15 s. Inviable para target <500 ms / <2 s. `qwen3:1.7b` lo acerca a 1.5–3 s chat y 4–8 s tools — sigue lejos del target pero **honesto**.
- **Migración**: detectar `nvidia-smi` falla o VRAM=0 → bajar a 1.7b. Carter UI debe avisar "modo CPU degradado".
- **Plan B**: `granite4.1:3b-instruct` Q4 (~2 GB RAM, BFCL 60.8) si tool accuracy es prioritaria sobre velocidad. **Es el punto de equilibrio honesto** — sacrifica chat fluido por tools decentes en CPU.
- **Dual NO viable** en CPU: dos inferencias secuenciales degradan a >5 s incluso para chat trivial.

### 4.2 Perfil `low_vram_6gb` (4.8 GB usables)

- **Recomendado: NO migrar. Mantener `qwen3:4b-instruct-2507-q4_K_M`.**
- Status quo Carter ya validado al 90% en matriz 18×30. BFCL ~62%, multilingüe ES/EN top de su categoría.
- **Dual técnicamente cabe** (qwen3:0.6b 0.5 GB + qwen3:4b 2.5 GB + KV 1.5 GB = 4.5 GB) pero el chat handler `qwen3:0.6b` no es competitivo en español ni en chat-fluido — solo serviría de router (estrategia B), y ya descartamos esa estrategia.
- **Plan B (mejora marginal)**: `granite4.1:3b-instruct` Q5_K_M (~2.3 GB) — BFCL 60.8 vs ~62% Qwen3-4B. **No mejora**. Mantén Qwen3-4B.
- **Trigger de cambio futuro**: cuando salga `qwen3.5:4b-instruct-2507` (ya hay 0.8B/2B/4B/9B en Unsloth docs, mejor tool-calling tras fix de chat template). Probar y comparar.

### 4.3 Perfil `balanced_8gb` (6.4 GB usables)

- **Recomendado: SINGLE `qwen3:4b-instruct-2507-q6_K` o `qwen3:8b-instruct-2507-q4_K_M`.**
- Q6_K de 4B (~3.2 GB + 1.5 GB KV = 4.7 GB) gana ~2–3 puntos accuracy vs Q4 a coste de ~10% velocidad. Cumple target.
- **Alternativa: `qwen3:8b-instruct-2507` Q4_K_M** (~5 GB + 1.5 KV = 6.5 GB, justo al límite del usable). Más lento (TTFT chat ~500 ms en hardware mid) pero BFCL ~65%.
- **Dual NO recomendado**: cabe (qwen3:0.6b + qwen3:4b + qwen3:4b-tools = 5.5 GB) pero el cuello serializa según #14578 y la mejora de tool accuracy de "qwen3:4b solo" → "qwen3:4b chat + qwen3:4b tools" es **literalmente cero** (mismo modelo, ambos llamados). Solo tendría sentido con 2 modelos diferentes y aquí no hay ese privilegio.
- **Plan B**: `granite4.1:3b-instruct` Q5 (~2.3 GB) — más conservador en VRAM, BFCL similar.

### 4.4 Perfil `balanced_10gb` (8 GB usables) — primer punto donde gana migrar

- **Recomendado: SINGLE `granite4.1:8b-instruct` Q4_K_M.**
- VRAM: 5.3 GB modelo + ~1.8 GB KV (8K ctx) = 7.1 GB → cabe.
- **BFCL-v3: 68.27%** (oficial IBM/Berkeley) vs ~62% del Qwen3-4B status quo → **+6 puntos = +9.7% relativo en accuracy**. Cerca del trigger de migración 10%.
- **Latencia**: TTFT chat 350–500 ms (cumple <500 ms), TTFT tool 1.0–1.8 s (cumple <2 s). En hardware mid-range (RTX 3060): ~28–35 tok/s para 8B Q4 (Hardware Corner data).
- **Multilingüe ES/EN**: Granite 4.1 entrenado con instrucción multilingüe, comparable a Qwen en ES (no hay benchmarks ES específicos publicados, pero IBM declara competencia con Gemma/Qwen en multilingüe — probar empíricamente con el smoke test 18×30 de Carter).
- **Dual NO compensa**: en 8 GB usables, dual obligaría a `granite4.1:3b` (3 GB) + `qwen3:4b` (2.5 GB) + KV (~1.5 GB total) = 7 GB. Pero esa configuración te da BFCL ~62% (qwen3:4b tools) — peor que single granite 8B (68.27%). El dual aquí lo único que añadiría es chat más fluido en 3B, lo cual ni siquiera mejora vs Qwen3-4B en español.
- **Migración recomendada**: granite4.1:8b. **Plan B si granite resulta peor en español**: quedarse con qwen3:4b o probar `qwen3:8b-instruct-2507` Q4 (BFCL ~65%, multilingüe top).

### 4.5 Perfil `high_quality_12gb` (9.6 GB usables)

- **Recomendado: SINGLE `granite4.1:8b-instruct` Q5_K_M** o `qwen3:8b-instruct-2507` Q5_K_M.
- VRAM granite Q5: ~6.5 GB + 2.5 KV = 9 GB. Cumple.
- BFCL 70%+ esperado (Q5 mantiene calidad casi igual a FP16).
- **Dual posible pero no rentable**: qwen3:4b (2.5 GB) + granite4.1:8b (5.3 GB) + 2 KV (~3 GB) = 10.8 GB → **excede usable 9.6 GB**, hay que bajar contextos a 4K. Y la ganancia es: chat más fluido (qwen3:4b vs granite4.1:8b en chat trivial) — pero granite ya cumple <500 ms TTFT chat. Ganancia mínima.
- **Migración**: granite4.1:8b Q5_K_M. **Plan B**: qwen3:8b-instruct-2507 Q5 si hay regresión en español.

### 4.6 Perfil `high_quality_16gb` (12.8 GB usables) — el del usuario

- **Recomendado: SINGLE `granite4.1:8b-instruct` Q6_K** (~8 GB) + headroom para verifier (numpy frame-diff, Win32 hooks, posibles embeddings nomic-embed-text si haces RAG).
- Si quieres ir dual aquí: qwen3:4b-instruct-2507 (chat, 2.5 GB) + granite4.1:8b (tools, 5.3 GB) + 2 KV (~3 GB) = 10.8 GB → **cabe cómodo**.
  - **Pero**: requiere 2 `ollama serve` para evitar serialization #14578.
  - Ganancia accuracy: tools delegado a granite (BFCL 68.27) vs qwen3:4b tools (BFCL ~62) = +6 pts BFCL. **Cumple trigger de migración.**
  - Ganancia latencia chat trivial: TTFT 250 ms (qwen3:4b) vs 400 ms (granite 8B). Ganancia ~37%, cumple trigger.
- **Decisión razonada**:
  - Si te importa **mínima complejidad operacional**: SINGLE granite4.1:8b Q6_K. Fin.
  - Si te importa **squeeze máximo**: DUAL qwen3:4b chat + granite4.1:8b tools, en **2 daemons Ollama** distintos puertos. Exige cambio en `agent.py` para hablar a 11434 (chat) y 11435 (tools).
- **Recomendación neta**: **SINGLE granite4.1:8b Q6_K**. La complejidad de 2 daemons + coherencia entre modelos no justifica el +37% TTFT chat trivial cuando el target <500 ms ya se cumple.

### 4.7 Perfil `top_tier_24gb` (19 GB usables) — único donde dual gana claro

- **Recomendado: DUAL** `qwen3:4b-instruct-2507` (chat, 2.5 GB) + `granite4.1:30b-instruct` Q4_K_M (~18 GB tools) en **2 daemons Ollama**.
- VRAM total: 2.5 + 18 + 2.5 KV ≈ 23 GB → ajustado pero cabe en 24 GB físico (deja ~1 GB headroom).
- **BFCL-v3: 73.68%** (granite4.1:30b lidera open en BFCL-v3 abr-2026) vs ~62% del status quo Qwen3-4B → **+11.7 pts = +18.9% relativo en accuracy. CUMPLE TRIGGER.**
- TTFT chat: 200–350 ms (qwen3:4b en RTX 4090 ~104 tok/s para 8B → ~150 tok/s para 4B Q4).
- TTFT tool: 2–3.5 s (granite 30B Q4 en RTX 4090 ~25–30 tok/s).
- **Alternativa SINGLE: `granite4.1:30b` solo**. Cabe (~18 GB), funciona, pero TTFT chat trivial ~1.5–2.5 s — viola target <500 ms. Solo viable si Carter acepta degradación de chat en favor de simplicidad.
- **Alternativa SINGLE-thinking**: `qwen3:30b-a3b-thinking-2507` Q4 (~18 GB MoE, 3B activos) — BFCL ~73%, MUY rápido (3B activos). **Pero issue #10976 lo bloquea para tools.** Descartado.
- **Alternativa SINGLE: `gpt-oss:20b`** (~12 GB MXFP4) — TauBench fuerte pero parser harmony bugs (#11991). Probar empíricamente; si funciona en tu workflow, es mejor que dual por simplicidad.
- **Triple posible?** En 24 GB físico, triple (qwen3:0.6b router + qwen3:4b chat + granite4.1:30b tools) = 21 GB → cabe pero el router LLM no aporta vs regex (sección 2). No recomendado.

---

## 5. Plan de migración (cuando dual gana — solo 24 GB)

### 5.1 Cambios en arquitectura
1. **Detección hardware en arranque** (`config/hardware_profile.py`): leer VRAM con `pynvml` o WMI, mapear a perfil, cargar config correspondiente.
2. **Si dual activado**: lanzar 2 `ollama serve` (script PowerShell `start-carter-ollama.ps1`):
   ```
   ollama serve --port 11434  (chat: qwen3:4b-instruct-2507)
   ollama serve --port 11435  (tools: granite4.1:30b-instruct)
   ```
   con `OLLAMA_MODELS` apuntando al mismo dir y `OLLAMA_KEEP_ALIVE=-1` en ambos servicios.
3. **`agent.py` cambios**:
   - Dos clientes Ollama: `chat_client` (11434), `tool_client` (11435).
   - Router regex (`router/structural.py`): ~150 LOC, devuelve `"chat" | "tool"`.
   - Memoria compartida: el último mensaje del chat (truncado a 200 tokens) se prepende como contexto al system prompt de tools cuando el router decide tool. NO el historial completo (eso introduce cruce de contextos y multiplica tokens).
   - Coherencia: tools NO genera prosa de "voy a buscar"; solo emite `tool_call`. La prosa la añade chat después de recibir `tool_result`. Esto evita el escenario de mentira (problema 5 del brief).

### 5.2 Coordinación entre 2 modelos (problema 5 del brief)
- **Frameworks publicados aplicables**:
  - **LangGraph supervisor** (`langgraph-supervisor-py`): handoff explícito entre agents, comparte state, soporta short/long-term memory. Maduro en mayo 2026.
  - **CrewAI router-agent**: similar, más opinionado.
  - **AutoGen**: pesado para Carter, no recomendado.
- **Patrón Carter recomendado (sin framework, código propio)**:
  - **Shared memory**: turn-buffer de 6 últimos mensajes (3 user + 3 assistant), pasado como `messages` a ambos modelos. NO el `<think>` block del thinking model si lo hubiera.
  - **System prompt de tools**: incluir nombre user, idioma detectado, último intent regex-clasificado, y la lista de 55 tools de Carter. **NO incluir la respuesta previa del chat model** — solo la consulta original del user. Esto fuerza a que tools sea "ground truth" sobre el mundo (ejecuta o no ejecuta) y chat sea "narrador honesto" (informa lo que tools devolvió, sin inventar).
  - **Consistencia anti-mentira**: chat NUNCA promete acciones futuras. Si tools devuelve error, chat lo reporta literal. Esto es el principio de Carter "honestidad por construcción" extendido al dual.

### 5.3 Implementaciones reales de referencia
- **Continue.dev** (docs.continue.dev/customize/deep-dives/autocomplete): patrón canónico con `roles: [chat]` y `roles: [autocomplete]` en config.yaml para 2 modelos en Ollama. Funciona porque autocomplete y chat NO se llaman en paralelo (autocomplete dispara on-keystroke, chat on-enter). Carter es similar: chat y tools son **mutuamente exclusivos en cada turno**, no concurrentes.
- **Open-Interpreter / Cline**: usa modelo único; no es referencia dual.
- **RA.Aid**: usa modelos diferentes para "expert" vs "default" tasks pero todos a través del mismo Ollama daemon — sufre del bug #14578 si se ejecutan en paralelo.

### 5.4 Cómo medir empíricamente la migración
1. Ampliar la matriz 18×30 actual de Carter a un **set de 90 casos**: 30 chat-trivial (saludo, charla, preguntas factuales), 30 tool-mono (un solo tool, pe. open_app), 30 tool-multi (cadena ReAct ≥2 tools).
2. **Métricas por caso**:
   - `tool_accuracy` (verifier estructural pasa = 1, falla = 0).
   - `tool_correct_args` (los args inferidos coinciden con ground-truth).
   - `chat_TTFT` (ms hasta primer token).
   - `tool_TTFT` (ms hasta primer tool_call emitido).
   - `total_turn_latency` (ms hasta fin de turno).
   - `lie_detected` (chat dice X pero tools no ejecutó X).
3. **Comparar**: status quo qwen3:4b vs candidato (granite8b single, dual...) en mismo set.
4. **Gates de migración**:
   - tool_accuracy: candidato debe ser ≥ status quo + 5 pts (P95 con bootstrap, n≥30 por categoría).
   - chat_TTFT P50 candidato ≤ status quo × 1.1.
   - lie_detected en candidato = 0 (no negociable).

---

## 6. Plan B si dual no gana (todos los perfiles ≤16 GB)

Por perfil, el "Plan B" es el modelo SINGLE que maximiza accuracy + velocidad sin dual:

| Perfil | Plan A (recomendado) | Plan B (alternativo) | Plan C (conservador) |
|---|---|---|---|
| 0 GB | qwen3:1.7b Q4 | granite4.1:3b Q4 | qwen3:0.6b (acepta degradación) |
| 6 GB | qwen3:4b-instruct-2507 Q4_K_M | qwen3:4b Q5_K_M (si VRAM holga) | granite4.1:3b Q5 |
| 8 GB | qwen3:4b Q6_K | granite4.1:3b Q6 | qwen3:4b Q4 (status quo) |
| 10 GB | granite4.1:8b Q4_K_M | qwen3:8b-instruct-2507 Q4 | qwen3:4b Q6_K |
| 12 GB | granite4.1:8b Q5_K_M | qwen3:8b-instruct-2507 Q5 | granite4.1:8b Q4 |
| 16 GB | granite4.1:8b Q6_K | qwen3:8b-instruct-2507 Q6 | mistral-nemo:12b Q4 (mejor multilingüe ES si granite/qwen flaquean) |
| 24 GB | DUAL qwen3:4b + granite4.1:30b Q4 | granite4.1:30b Q4 SINGLE | qwen3:8b-instruct-2507 Q8 (~9 GB, premium quality) |

**Principio operacional**: **Q5_K_M y Q6_K casi siempre vencen a Q4_K_M** en accuracy (1–3 puntos BFCL extra) si VRAM holga. **No bajes nunca de Q4_K_M** en producción — Q3/Q2 dañan tool calling AST severamente (Unsloth docs, BFCL evaluations).

---

## 7. Speculative decoding / draft models (sección 9)

### 7.1 Estado en Ollama, mayo 2026
- **PR #8134** (autor bfroemel) implementa speculative decoding generic en Ollama. **Sigue sin mergear** en mayo 2026 a pesar de PRs upstream (`OLLAMA_DRAFT_GPU_DEVS`, model Modelfile field para draft, memory estimation).
- **Issue #5800 / #9216**: requests recurrentes desde 2024, sin compromiso de fecha.
- **Lo único que existe**: Ollama **0.23.x (mayo 2026)** soporta **Gemma 4 MTP speculative decoding SOLO en macOS/MLX** (via `ollama run gemma4:31b-coding-mtp-bf16`). NO en Windows ni Linux ni Nvidia.
- **Veredicto**: para Carter en Windows con Ollama, speculative decoding **NO es opción en mayo 2026**. Ignorar como factor de diseño.

### 7.2 Si quisieras igual (ruta llama.cpp directa)
Dejarías Ollama y montarías `llama-server` con `--model` + `--model-draft`:
- **Pares draft + target con tokenizer compatible**:
  - target `qwen3:8b-instruct` ← draft `qwen3:0.6b` o `qwen3:1.7b` (mismo vocab Qwen3 151,936).
  - target `qwen2.5-coder:32b` ← draft `Qwen2.5-Coder-DRAFT-0.6B-Q4_0.gguf` (oficial Salesforce/community); reportado **4× speedup en RTX 5000 Ada** para coding refactoring (llama.cpp #10466).
  - target `qwen3.6:27b` ← draft `qwen3.5:0.8B`: en RTX 3090, **regression −3% a −12%** en mainline llama.cpp recientes (2026-04-22 followup bench, github thc1006/qwen3.6-speculative-decoding-rtx3090). **No funciona como esperabas** en Ampere consumer + MoE.
  - target `granite4.1:30b` ← draft `granite4.1:3b`: NO testado públicamente; tokenizers compatibles (mismo IBM Granite family); especulativo.
- **Speedup esperado en tool calling**: el JSON estructurado tiene alta predictibilidad → en teoría 2–3× speedup (high draftability prompts). En la práctica los benchmarks recientes muestran resultados muy variables (1× a 4× según hardware y MoE vs dense).
- **Trade-off VRAM**: draft Q4 de 0.6–0.8B añade ~0.5–1 GB. En 12/16 GB margen suficiente; en 24 GB con granite4.1:30b ya ajusta no cabe el draft.

### 7.3 Alternativas si quieres speedup hoy
1. **vLLM** (no Ollama): `--speculative-config '{"method": "mtp", "num_speculative_tokens": 1-2}'` para Qwen3.5+. **Pero no es la stack Ollama** y el usuario fija Ollama 0.20.4+.
2. **LM Studio** (en Windows): GUI de speculative decoding, soporta llama.cpp backend. **Tampoco es Ollama.**
3. **Esperar Ollama 0.24+ o 0.25+**: el PR #8134 lleva meses, podría mergearse. Vigilar release notes.
4. **Optimizaciones que SÍ están disponibles en Ollama 0.20.4+ y mejoran latencia**:
   - `OLLAMA_FLASH_ATTENTION=1` (default ya en builds modernas).
   - `OLLAMA_KV_CACHE_TYPE=q8_0` o `q4_0` (cuadruplica context al mismo VRAM, calidad ligeramente reducida).
   - `num_predict=-1` (evita truncation bug #14570).
   - `num_ctx` ajustado (reducir de 256K a 8K si Carter no usa long context — ahorra GBs de KV).

### 7.4 ¿Speculative decoding cambia las recomendaciones por perfil?
**NO en mayo 2026** porque no está disponible en Ollama Windows. Cuando se merge (probablemente Q3-Q4 2026 si los PRs avanzan):
- **12/16 GB**: añadir `qwen3:0.6b` como draft de `granite4.1:8b` o `qwen3:8b-instruct-2507` podría dar 1.5–2× en tool calling (alta draftability JSON). Tendría sentido.
- **24 GB**: draft `granite4.1:3b` de target `granite4.1:30b` mejoraría TTFT tool de ~3 s a ~1.5 s, cerrando el gap con dual y haciendo single-30B viable como única recomendación.
- **≤10 GB**: no hay headroom para draft + target juntos, sin cambio.

**Acción concreta cuando llegue**: re-evaluar perfiles 12+ con draft `qwen3:0.6b` (~0.5 GB extra) y comparar TTFT tool. Si gana >30%, integrar. Hasta entonces, no diseñar para algo que no existe.

---

## 8. Caveats y honestidad

### 8.1 Lo que NO se ha verificado empíricamente (riesgos)
- **Granite 4.1 en español**: IBM publica scores multilingüe agregados pero no benchmark ES específico. Los 18×30 casos de Carter validaron Qwen3-4B; **antes de migrar a Granite 4.1:8b en cualquier perfil ≥10 GB, Carter debe correr la misma matriz** y comparar tool_accuracy + chat_quality_es. Si granite resulta peor en ES (probable que Qwen sea superior — Qwen entrena con corpus chino-occidental dominante), volver a `qwen3:8b-instruct-2507`.
- **Granite 4.1:30b BFCL 73.68% es self-reported por IBM** sobre evaluación propia — leaderboard Berkeley actualizado abril 2026 lo confirma top open en su clase, pero "Qwen3-32B 75.7%" según PricePerToken es marginalmente superior. **`qwen3:32b-instruct-2507` Q4 (~19 GB) es alternativa válida en 24 GB y posiblemente mejor en ES**. No está en candidatos del brief original pero merece test.
- **Latencias TTFT estimadas** son extrapolaciones de benchmarks Hardware Corner / Database Mart en hardware RTX 3060/4060/4090. **Carter debe medir en su hardware real** — el RTX 3060 Q4 8B reportado 28–35 tok/s puede variar ±20% con drivers, CUDA versión, sistema operativo.
- **`gpt-oss:20b` con harmony**: hay reportes mezclados — funciona en algunos clientes, falla en otros. **No incluir en producción Carter sin smoke test de 50+ casos.**

### 8.2 Lo que es estrictamente honesto admitir

**El bottleneck de Carter, según esta investigación, NO es el modelo en perfiles ≤10 GB.** Es:
1. El parser de tool calls de Ollama (3 issues abiertos contra qwen3).
2. La serialización de requests entre modelos cargados (#14578).
3. La ausencia de speculative decoding cross-platform.
4. El prompt size (55 tools en system prompt es ~3K–5K tokens — eso es el 60% del budget de 25 s en muchos casos).

Optimizar el modelo (qwen3:4b → granite8b) gana 6 puntos BFCL pero **no resuelve los bugs**. **Antes de cambiar modelo, considera**:
- **Tool retrieval dinámico** (top-K=10 tools relevantes según embeddings de la consulta, no las 55) — reduce prompt 70%, latencia ~50%.
- **Forzar `num_predict=-1` y `keep_alive=-1`** explícitos en cada llamada Ollama.
- **Migrar a 2 daemons solo si dual** (no si single).
- **Evitar `qwen3:*-thinking` en tools** hasta que #10976 cierre.

### 8.3 La universalidad cross-hardware se respeta
Cada perfil tiene una respuesta diferente — el código de Carter debe detectar VRAM y aplicar perfil correspondiente:
- 0 GB → qwen3:1.7b single
- 6/8 GB → qwen3:4b-instruct-2507 single (status quo)
- 10/12/16 GB → granite4.1:8b single (migrar)
- 24 GB → dual qwen3:4b + granite4.1:30b (única configuración dual recomendada)

**Ningún setup dual mejora claramente qwen3:4b en perfiles ≤10 GB.** En 12/16 GB la mejora viene de **subir el modelo único, no de dualizarlo**. Solo 24 GB justifica dual.

### 8.4 Conclusión brutal
**Si solo lees una línea**: deja Carter con `qwen3:4b-instruct-2507-q4_K_M` hasta que tengas hardware ≥10 GB; en ese momento migra a `granite4.1:8b` single; solo si tienes 24 GB plantéate dual. **Speculative decoding no existe para tu stack en mayo 2026; no diseñes alrededor de él.** Los bugs de Ollama qwen3-tools son tu mayor riesgo, no la elección de modelo.

---

## Recomendaciones (orden de ejecución)

1. **Inmediato (sin migrar modelo)**:
   - Implementar router regex estructural (~150 LOC) si aún no existe — 0 ms overhead, mejora modularidad.
   - Forzar `keep_alive: -1` y `num_predict: -1` en todos los calls Ollama desde `agent.py`.
   - Detección hardware automática + tabla de perfiles (sección 1) en `config/hardware_profile.py`.
2. **Smoke test antes de migrar nada**: ampliar matriz 18×30 → 90 casos con métricas BFCL-style + lie_detected.
3. **Si VRAM detectada ≥10 GB**: pull `granite4.1:8b-instruct` Q4_K_M, correr smoke test, comparar contra qwen3:4b actual.
4. **Si VRAM ≥24 GB y smoke test confirma ganancia**: pull `granite4.1:30b-instruct` Q4_K_M, montar 2 daemons (puertos 11434/11435), tests de coherencia anti-mentira.
5. **Vigilar Ollama releases**: cuando #10976 (qwen3-thinking + tools) cierre → re-evaluar `qwen3:4b-thinking-2507` (BFCL 71.2 superaría granite4.1:8b 68.27 en 6/8 GB). Cuando PR #8134 mergee → re-evaluar speculative en 12+.
6. **NO migrar a dual en ≤16 GB** salvo que un test futuro contradiga. **NO usar `xLAM-2-8b-fc-r` en Ollama** (no registra tools). **NO usar `qwen3:4b-thinking` con tools** hasta fix #10976.

### Thresholds que cambiarían las recomendaciones
- Si granite4.1:8b en español (test interno Carter) baja >5 pts vs qwen3:4b → quedarse con qwen3 family (qwen3:8b-instruct-2507 en 10+ GB).
- Si Ollama merge speculative decoding (vigilar v0.24+) → re-test 12+/24 GB con drafts.
- Si sale `qwen3.5:8b-instruct-2507` en Ollama oficial → testear; probable nuevo SOTA en su clase.
- Si BFCL-v4 (que añade web search/memory) cambia rankings → re-evaluar; v3 sigue siendo el cross-comparison estándar mayo 2026.

---

## Caveats finales (resumen)

- **Toda predicción de TTFT es ±25%** según hardware exacto, drivers y carga de Windows. Los números de la tabla 1 son orientativos para hardware mid-range.
- **Los BFCL-v3 scores** son self-reported (Granite IBM, Salesforce xLAM) o de Berkeley (Qwen3); en producción Carter, **el verifier estructural de Carter ES tu BFCL-v3 real** — un score off-the-shelf no garantiza que Carter funcione mejor.
- **Issues Ollama abiertos** mencionados (#10976, #11232, #14570, #14578) pueden cerrarse en cualquier momento. Verificar antes de producción final con `gh issue view <num>`.
- **Ollama 0.20.4+ "obligatorio"**: la investigación cubre estado mayo 2026. Si en tu instalación corres 0.18 o 0.16, comportamiento puede diferir (especialmente bugs de parser harmony y qwen3 tool parser que se han ido refinando). Recomendado upgrade a 0.23.x para Mac (speculative MTP) o última 0.20+ stable para Windows.
- **Datos Qwen3 0.6b/1.7b multilingüe ES**: no hay benchmark dedicado público. Qwen3 declara soporte 119 idiomas con corpus equilibrado; en práctica, modelos <2B suelen degradar fuerte en ES vs EN. **Test empírico antes de comprometer cpu_fallback.**
- **`mistral-nemo:12b`** descartado en recomendaciones principales: function calling oficial Mistral, fuerte en ES, pero no aparece en BFCL-v3 leaderboard top open (Granite/Qwen lo superan en 2026). Mantener como Plan B en 16 GB si granite/qwen fallan en español.
- **El proyecto Carter valora honestidad sobre hype**: esta investigación concluye que la **migración dual no es la respuesta** salvo en 24 GB, y que **el camino de mayor ROI** no es cambiar arquitectura sino (a) tool retrieval dinámico, (b) configuración de keep_alive/num_predict, (c) subir modelo único en ≥10 GB.