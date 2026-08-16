# Carter v4 — Dossier Técnico Definitivo (Refactorización)

> **Dossier técnico-arquitectural para construir el asistente local Carter v4 sobre Windows + Ollama/llama.cpp, con presupuesto VRAM 6–24 GB y latencia tipo Alexa (<8 s en tareas simples).** Decisiones razonadas con benchmarks BFCL v3, papers arXiv 2024–2026 y comparativa con Claude Code, Goose, Cline, Aider, Devin y MCP.

---

## TL;DR

- **Modelo recomendado (decisión central):** sustituir el dúo `qwen2.5:7b` + `qwen3:8b` por **`qwen3:4b-instruct-2507` (no-thinking, Q4_K_M, ~3 GB) como default universal en 6–24 GB**, escalando a **`qwen3:14b`** o **`qwen3:30b-a3b-instruct-2507` (MoE, 3 B activos)** en 16–24 GB. `qwen3-4b-instruct-2507` ofrece BFCL v3 cercano al 71 % (su variante Thinking-2507 reporta 71.2 %), no-thinking obligatorio (mata el problema de latencia 7-21 s de qwen3:8b), tag oficial Ollama con `tools` nativo, multilingüe 100+ idiomas con buen español, y latencia esperable 0.5–2 s en RTX 4060 para tool-calls cortos. Granite 4.1 8B (BFCL 68.3, 512 K contexto) es la alternativa **conservadora** corporativa.
- **Loop:** mantener **ReAct single-thread tipo Claude Code "nO"** (un solo hilo, historia plana, máx. 2-3 reintentos, compaction al 70 % de `num_ctx`), **NO** migrar a multi-agent. Es lo que está validado a escala (Claude Code, Goose) y lo que ya tiene Carter v4. Plan-and-execute / ReWOO solo se justifica para misiones compuestas (sección 13). Honest-by-construction se logra con **structural reply rewriting** (no hay tool_call → no se permite afirmar éxito) + **AEGIS-style pre-execution firewall** (arXiv 2603.12621) + **AgentSpec rules** para destructivos (ICSE'26, arXiv 2503.18666).
- **Lo que NO es realista con 8 GB y <8 s:** 540/540 PASS REAL **no es alcanzable** simultáneamente con un único modelo de 7-8 B en 8 GB de VRAM. Las categorías GUI con apps CEF (Steam/Discord/Spotify), misiones multi-step largas, y verificación visual con VLM son las que rompen el budget. El dossier prescribe un **stack escalonado por VRAM tier** y una **matriz de aceptación honesta** que admite que ~5-8 % de casos GUI exigen 16 GB+ o degradación graciosa con UNVERIFIED.

---

## Key Findings

1. **Qwen3 split Instruct/Thinking-2507 resuelve el bloqueo de Carter v4.** El problema observado (qwen3:8b emite tools pero latencia 7-21 s) viene del modo thinking activado por defecto. Las variantes **`qwen3:Xb-instruct-2507`** publicadas por Qwen (julio-agosto 2025, presentes en Ollama como tags oficiales `qwen3:4b-instruct-2507-q4_K_M`, `qwen3:8b-instruct-2507`, `qwen3:14b-instruct-2507`, `qwen3:30b-a3b-instruct-2507`) son **non-thinking only** (`enable_thinking=False` ya no es necesario), preservan tool-calling Hermes-style nativo en Ollama, y tienen 256 K de contexto. Esto colapsa la latencia a rangos compatibles con <8 s.
2. **Ollama "does not support tools" se resuelve mirando el tag, no el modelo base.** Issues #5793, #9437, #10912, #12286, betterclaw blog confirman que el error viene del template del Modelfile, no del modelo. `watt-tool-8B` oficial (LLaMA-3.1-8B-Instruct fine-tuned, BFCL SoTA en su segmento) **no funciona vía Ollama nativo** porque su formato `[func_name(args)]` no coincide con el parser Hermes/Qwen del Ollama; existe `hengwen/watt-tool-8B` en Ollama pero la columna "tools" del registry no garantiza funcionamiento (issue #12286). Veredicto: descartar `watt-tool` para Carter v4 a menos que se migre a vLLM.
3. **BFCL v3 (Berkeley) es el benchmark de referencia, pero hay pitfalls.** Top global: GLM-4.5 (77.8 %) — fuera de rango VRAM. En el rango ≤14 B útil para Carter: **Qwen3-4B-Thinking-2507 = 71.2 %**, **Granite 4.1 30B = 73.68 %**, **Granite 4.1 8B = 68.3 %**, **Qwen3-Thinking ~71.9 %**, **GPT-OSS-20B ~67-68 %**. xLAM-7b-fc-r logró 88.24 % en BFCL v1 (julio 2024) pero **no en v3** y su formato no es compatible con Ollama tools. Hermes 4 14B (Qwen3-14B base, ChatML) sí es compatible Ollama pero introduce thinking opcional.
4. **Function-calling format óptimo:** **Hermes-style XML `<tool_call>{json}</tool_call>`** (estándar de facto de Qwen3, Hermes, mistral-tools-parser, qwen2.5-coder) supera al formato OpenAI puro en parse-rate cuando el modelo va por debajo de 13 B. Para máxima robustez añadir **GBNF / JSON Schema constrained decoding** vía `llama.cpp --grammar` o response_format json_schema; reduce parse-failures a ~0 % a costa de ~2-5 % de latencia. Combinado con Hermes XML alcanza la fiabilidad necesaria para "honest-by-construction".
5. **Anti fake-success se construye estructuralmente, no con re-prompts.** El paper survey arXiv 2509.18970 categoriza "tool-call hallucination" en selección y uso. El patrón válido ya identificado en literatura (AnswerAI "unauthorized tool call", Amazon arXiv 2601.05214 internal-representation detection) y validado empíricamente en Cline y Goose es: **(a)** detectar emisión de claims de éxito sin tool_call previo en la trace; **(b)** reescribir la respuesta a UNVERIFIED + propuesta de tool; **(c)** **nunca** re-prompt al modelo (confunde y aumenta latencia). Esto es exactamente lo que Carter v4 ya tiene parcialmente con su Auditor de 13 detectores, pero falta el paso (b) de reply rewriting.
6. **GUI apps CEF (Steam/Discord/Spotify):** la combinación AttachThreadInput + mouse_event + UIA AutomationElement.Invoke() **sigue siendo lo correcto** en 2025-2026; pywinauto issue #606 confirma que CEF no expone elementos al UIA tree porque Chrome necesita `--force-renderer-accessibility`. Solución universal sin AttachThreadInput **no existe** sin caer a VLM (OmniParser V2, ScreenSpot Pro 39.6 %). OmniParser V2 con qwen2.5-vl:7b es viable como **fallback** cuando UIA falla, pero añade 3-8 s por screenshot — incompatible con <8 s salvo en misiones, no en single-step.
7. **Memoria:** **SQLite + sqlite-vec** es la opción dominante para el perfil de Carter (single-user, local-only, presupuesto VRAM apretado). Letta filesystem benchmark mostró que un agente con search_files + answer_question alcanza 74 % en LoCoMo, superando Mem0 graph (68.5 %). Implementación recomendada: SQLite con tabla `memories(id, ts, role, content, embedding BLOB, scope, ttl)` + `bge-small-en-v1.5` o `intfloat/multilingual-e5-small` (embeddings CPU, ~30 ms/query, 384-dim, 100 MB).
8. **Speculative decoding y router multi-modelo no compensan.** En 8 GB de VRAM no caben dos modelos residentes simultáneamente con keep_alive=-1 (qwen3:4b Q4 = 3 GB + draft 0.6B = ~1 GB ya consume 4-5 GB con KV-cache). El overhead de carga al cambiar de modelo (3-8 s) **rompe el budget Alexa**. Recomendación: **un solo modelo + routing por reglas determinísticas pre-LLM** (regex/heurística trivial → respuesta canned para "hola/qué hora es", LLM para todo lo demás). Speculative decoding solo gana si tienes 24 GB+ y target ≥14 B.

---

## Details

### 1. Arquitectura óptima del Loop principal

| Patrón | Latencia | Uso correcto en Carter | Veredicto |
|---|---|---|---|
| **ReAct single-thread (Claude Code "nO")** | Baja por step (1 LLM call) | **Default v4** | ✅ Mantener |
| Plan-and-execute (LangGraph) | Alta (planner + executor) | Misiones multi-step explícitas | Solo subsistema |
| ReWOO | Mínima (2 LLM calls fijos) | Cuando todos los tools son independientes | No aplicable a chat conversacional |
| Reflexion / self-critique | 2-5x ReAct | Code-gen iterativo | No usar |
| Tree of Thoughts | 10x+ | Razonamiento puro | No usar |
| Multi-agent router | Carga × N modelos | Equipos especializados (Goose Teams) | No con 8 GB VRAM |
| LangGraph state machine | Media | Workflows con estado complejo | Sobreingeniería |

**Justificación arquitectural:** Anthropic Claude Code documenta explícitamente (case study ZenML, blog promptlayer.com) que su loop master "nO" es **single-threaded, flat history, while(toolCalls)**. La compactación dispara al 92 % del context window (compressor "wU2"). Carter v4 ya implementa esto con 423 LoC; **no migrar**.

**Refinamientos requeridos:**
- Compaction al 70 % de `num_ctx` (más conservador que Claude porque modelos locales degradan antes con context largo).
- Reintentos: máx. 3, con backoff: si tool_call falla 3x con mismo arg → declarar UNVERIFIED, no inventar.
- "h2A"-style asynchronous queue solo si voz fase 2 obliga.

### 2. Modelo LLM definitivo — Tabla comparativa

| Modelo | BFCL v3 | IFEval ES | VRAM Q4_K_M | Disponibilidad Ollama | Tool support | Thinking obligatorio | Latencia 4060 (tool turn) | ES-multilingüe |
|---|---|---|---|---|---|---|---|---|
| **qwen3:4b-instruct-2507** | ~70 % (proxy del 4B-Thinking 71.2 BFCL) | bueno (100+ idiomas) | ~3 GB | ✅ **nativo** (`qwen3:4b-instruct-2507`) | ✅ Hermes-style nativo | ❌ no-thinking only | **0.5-1.5 s** | ✅✅ |
| **qwen3:8b-instruct-2507** | ~70-72 % | excelente | ~5.5 GB | ✅ nativo | ✅ | ❌ | 1-2.5 s | ✅✅ |
| **qwen3:14b-instruct-2507** | ~74 % | excelente | ~9 GB | ✅ nativo | ✅ | ❌ | 2-4 s | ✅✅ |
| **qwen3:30b-a3b-instruct-2507** (MoE 3B activos) | ~75 % | excelente | ~18 GB (FP4) o ~17 Q4 | ✅ nativo | ✅ | ❌ | 1.5-3 s (sólo 3 B activos) | ✅✅ |
| qwen3:8b (default thinking on) | 71.9 % | excelente | 5.5 GB | ✅ | ✅ | ⚠️ default | **7-21 s** ❌ | ✅✅ |
| qwen2.5:7b-instruct | ~62 % | bueno | 4.7 GB | ✅ | ⚠️ a veces no emite tools en pedidos sutiles | no | 0.4-1 s | ✅ |
| **granite4.1:8b-instruct** | 68.3 | bueno | 5 GB | ✅ nativo | ✅ | no | 1-2 s | ✅ (200+ embed) |
| granite4.1:30b-instruct | 73.68 | bueno | ~18 GB | ✅ nativo | ✅ | no | 2-4 s | ✅ |
| granite3.3:8b | ~65 % | medio | 5 GB | ✅ | ✅ | no | 1-2 s | medio |
| **gpt-oss:20b** (MoE 3.6B) | ~67-68 % | medio | ~13 GB MXFP4 | ✅ nativo | ✅ (Harmony format, parser oficial) | adjustable low/mid/high | 1-2 s | medio (English-mostly) |
| llama3.1:8b | ~58 % | medio | 4.7 GB | ✅ | ✅ | no | 0.8-1.5 s | medio |
| llama3.3:70b (Q3_K_M) | ~65 % | bueno | ~32 GB ❌ | ✅ | ✅ | no | n/a | bueno |
| mistral-small:24b (3.2) | ~60 % | bueno | ~14 GB | ✅ | ✅ | no | 3-7 s | bueno |
| mistral-nemo:12b | ~55 % | medio | 7.5 GB | ✅ | ✅ | no | 1.5-3 s | bueno |
| phi-4:14b | ~58 % | medio | 9 GB | ✅ | ⚠️ tools roto en 0.5.13 (#9437) | no | 1.5-3 s | medio |
| phi-4-mini (3.8B) | ~55 % | medio | 2.5 GB | ✅ con caveats | ⚠️ #9437 reportado, requiere parser custom | no | 0.5-1 s | medio |
| gemma2:9b | n/a | medio | 5.5 GB | ✅ pero **no tools** (issue n8n) | ❌ | no | n/a | bueno |
| gemma3:12b | n/a | medio | 7 GB | ⚠️ "does not support tools" | ❌ | no | n/a | bueno |
| **hermes3:8b-llama3.1** | ~63 % | bueno | 5 GB | ✅ nativo | ✅✅ Hermes formato canónico | no | 1-2 s | medio |
| **hermes-4:14b** (Qwen3-14B base) | n/a public BFCL | bueno | 9 GB | ⚠️ comunidad GGUF | ✅ Hermes XML | hybrid | 2-4 s | bueno |
| hermes-4:70b | n/a | bueno | ~40 GB ❌ | comunidad | ✅ | hybrid | n/a | bueno |
| command-r:7b | ~60 % | bueno | 4.5 GB | ✅ | ✅ | no | 0.8-2 s | bueno (multilingüe Cohere) |
| command-a:32b (rebrand) | n/a | bueno | ~20 GB | ✅ | ✅ | no | 3-6 s | excelente |
| functionary:7b | ~55 % v1 (legacy) | medio | 4.5 GB | comunidad | ✅ | no | 0.8 s | medio |
| **xLAM-7b-fc-r** | 88.24 (v1, no v3) | bajo | 4.5 GB | **roto en Ollama** (formato `[func()]` no parsea) | ⚠️ vllm-only | no | n/a | bajo |
| **watt-tool-8B** | SoTA en su tier | medio | 5 GB | ⚠️ `hengwen/watt-tool-8B` existe pero cuestionado | requiere prompt completo en system | no | n/a | medio |
| ToolACE-8B | ~75 % | medio | 5 GB | comunidad GGUF | vllm-only | no | n/a | medio |
| Hammer-7B | high (BFCL paper) | medio | 4.5 GB | comunidad | vllm-preferred | no | n/a | medio |
| DeepSeek-V3 | n/a en local | n/a | enorme | ❌ no aplica | n/a | n/a | n/a | n/a |
| deepseek-r1:8b-qwen3 | n/a | medio | 5 GB | ⚠️ #10912 "does not support tools" en Ollama | ❌ | thinking | n/a | bueno |
| GLM-4.7-Flash 30B | top BFCL family | bueno | ~18 GB | ✅ nativo (oct 2025) | ✅ | adjustable | 2-4 s | bueno |

#### Recomendación TOP 3 por VRAM tier

**6 GB tier (RTX 3060 6GB / GTX 1660 / laptops):**
1. **CONSERVADORA = AGRESIVA: `qwen3:4b-instruct-2507` Q4_K_M (~3 GB)**. Comando: `ollama pull qwen3:4b-instruct-2507`. Riesgos: ninguno conocido; tag oficial Qwen, tracking estable desde julio 2025.
2. Alternativa: `granite4.1:3b-instruct` (BFCL ~60 %, 200+ idiomas embeddings).
3. Bajada: `qwen2.5:3b-instruct` (legacy, peor BFCL).

**8 GB tier (RTX 3060 8GB / 4060 8GB / 3070):**
1. **CONSERVADORA: `granite4.1:8b-instruct` Q4_K_M (5 GB).** BFCL 68.3, dense, sin thinking, 512 K context, tool calling nativo OpenAI-compatible. Comando: `ollama pull granite4:8b` (o `granite4.1` cuando Ollama lo publique tras 29 abr 2026).
2. **AGRESIVA: `qwen3:8b-instruct-2507` Q4_K_M (5.5 GB).** BFCL ~70-72, multilingüe superior, Hermes tools. Comando: `ollama pull qwen3:8b-instruct-2507`. Riesgos: con 8 GB físicos y ~5.5 GB modelo + 1-2 GB KV-cache estás al límite; KV-cache `q8_0` cuasi-obligatorio.
3. **Fallback: `qwen3:4b-instruct-2507`** (siempre cabe, deja headroom para ASR/embedding).

**16 GB tier (RTX 4070 Ti Super / 4080 / 5060 Ti):**
1. **CONSERVADORA: `granite4.1:8b-instruct`** (probado, dejar 8+ GB para VLM + ASR + embeddings residentes).
2. **AGRESIVA: `qwen3:14b-instruct-2507` Q4_K_M (~9 GB)** + qwen2.5-vl:3b (~3 GB) + bge-small (CPU). BFCL ~74, latencia 2-4 s.
3. **Experimental: `qwen3:30b-a3b-instruct-2507`** Q3_K_M (~14 GB), MoE con solo 3 B activos → latencia 1.5-3 s pese a 30 B totales. **Riesgo concreto:** consumo de KV-cache crece con 256 K context si no fijas `num_ctx=8192`.

**24 GB tier (RTX 3090 / 4090 / 5090):**
1. **CONSERVADORA: `qwen3:14b-instruct-2507`** + VLM dedicado (qwen2.5-vl:7b, ~6 GB) + embeddings GPU.
2. **AGRESIVA: `qwen3:30b-a3b-instruct-2507` Q4_K_M (~18 GB)**. BFCL 75, MoE 3B activos = latencia 1.5-3 s comparable a 7B. Comando: `ollama pull qwen3:30b-a3b-instruct-2507`.
3. **Especializada agente: `granite4.1:30b-instruct` Q4_K_M (~18 GB).** BFCL 73.68, 512 K context, sin thinking. Riesgos: no-MoE → latencia 3-5 s en tool-call corto.

#### Alternativa fine-tune

**No recomendado para Carter v4 ahora.** Razones:
- BFCL v3 ya está casi saturado por Qwen3-Thinking-2507 a nivel ≤14 B (71-72 %); el techo de mejora vía LoRA sobre tu dominio es ~3-5 % BFCL.
- El dataset agéntico real-world Carter (33 tools, multilingüe + typos, follow-ups, anti-trampas) requeriría 5-20 K ejemplos curados → 2-3 semanas de trabajo + GPU rental.
- Si en 12 semanas quedan gaps específicos en categorías memoria/identidad, considerar **LoRA SFT sobre `qwen3:4b-instruct-2507` con dataset teacher-student** generado por `qwen3:30b` o GPT-4o como teacher, validado contra BFCL multi-turn. Stack: Unsloth + Axolotl, ~$50-100 RunPod.

### 3. Estrategia multi-modelo

**Decisión: UN modelo principal + pre-LLM rule router.** Datos:
- Cargar dos modelos residentes en 8 GB con `keep_alive=-1` no es viable con ningún par útil (qwen3:4b + granite4:8b = 8.5 GB).
- Switch entre modelos no residentes en Ollama: 3-8 s de carga (modelfile + GGUF mmap), **rompe budget Alexa**.
- Goose, Open Interpreter y Cline usan **un único modelo** y sólo recurren a routing por LLM cuando hay multi-tier (Sonnet planner + Haiku executor) — eso es nube, no aplica.
- Speculative decoding: con Qwen3-4B target + Qwen3-0.6B draft consigues ~1.4-1.8x acceleration en H100 (DART paper 2601.19278), pero en RTX 4060 8 GB el draft consume VRAM crítica y la mejora se evapora.

**Patrón recomendado:**
```
user_text → cheap_router (regex/keyword + length) →
  [intent=trivial_chat → respuesta corta canned + sentence-transformers similarity para "Carter, ¿qué eres?"]
  [intent=tool_likely → LLM principal con tools]
```
El router cheap es **determinístico, no LLM**, latencia <5 ms. Cubre ~30 % del tráfico (saludos, identidad, hora) sin tocar Ollama.

### 4. Function-calling format

| Formato | Parse-rate ≤8 B | Latencia overhead | Recovery | Recomendación |
|---|---|---|---|---|
| OpenAI JSON nativo | 70-85 % en modelos no-finetune | ~0 % | regex retry | Solo si tu modelo está finetuneado para él (Llama 3.1 native, Granite) |
| **Hermes XML `<tool_call>{json}</tool_call>`** | **88-95 %** | tokens marker (~5-10) | streaming-friendly | **✅ ELEGIDO** |
| Anthropic XML `<tool_use>` | 90 % en Claude | n/a | n/a | No aplica local |
| Llama 3.1 native | 85 % en Llama-tuned | low | medium | Solo Llama-stack |
| Granite tool format | 90 % (Granite 4.x) | low | clean | Solo Granite |
| xLAM `[func(args)]` | 90 % en xLAM | n/a | break-prone | **NO** (Ollama-incompatible) |
| **GBNF / JSON Schema enforcement** | **~99-100 %** | +2-5 % latencia | imposible fallar estructura | ✅ usar **encima** de Hermes |

**Veredicto Carter v4:** Hermes XML como formato wire (compatible nativo con qwen3 y hermes3 en Ollama) + **opcional `format: "json"` o `response_format: {type: "json_schema"}` en Ollama 0.6+** para los argumentos de tools críticos (sandbox FS, terminal). Esto reduce parse failures observados (44/44 unit tests verde sugiere parser ya robusto) a indistinguibles de cero.

### 5. System prompt estrategia

**Datos comparativos:**
- Mark XXXIX (~150 tokens): minimalista, alta variabilidad.
- Carter v3 (~1500): rigorista, baja regurgitation pero 600 ms más de eval.
- Carter v4 v8 (~600): el sweet spot empíricamente.
- Goose: ~400-600 tokens + tool catalog inyectado dinámicamente.
- Cline: ~800 tokens incluyendo "instructions about being honest about uncertainty".
- Aider: ~300 tokens role-focused.
- Cursor: ~500 tokens + per-file context.
- Open Interpreter: ~250 tokens, muy directo.

**Hallazgos clave para modelos ≤13 B:**
- Prompts >1200 tokens degradan recall de tools en ~8-12 % (Hermes regurgitation).
- Few-shot examples (1-3) en system mejoran tool-call accuracy ~5 % pero suben latencia ~200 ms; **NO recomendado para Carter** dado budget.
- Inyectar tool catalog en `system` (no en `user`) preserva prefix cache de Ollama (17.7x speedup verificado en leanpub.com/ollama).

**Recomendación específica (~600 tokens distribuidos):**
1. **Identidad** (50 tok): "Eres Carter, asistente local..."
2. **Honest-by-construction contract** (120 tok): "Si una acción requiere herramienta, llamá la herramienta. Si no la llamás, no afirmes que la hiciste. Si una herramienta falla 3 veces, devuelve UNVERIFIED."
3. **Idiomas y tono** (40 tok): "Respondé en el idioma del usuario (ES/EN). Conciso."
4. **Confirmaciones destructivas** (80 tok): "Antes de eliminar/cerrar/escribir-fuera-sandbox preguntá: '¿Confirmás X?'."
5. **Tools** (resto, dinámico inyectado por adapter Ollama, ~300 tok para 33 tools): el formato Hermes ya provisto por chat template de qwen3.
6. **NO incluir:** keyword lists per-app, ejemplos few-shot, listas largas de "no hagas X".

### 6. Verificación post-acción

Para cada categoría, **verifier estructural inline** (mismo proceso, sin segundo LLM call):

| Tool category | Pre-execution check (AEGIS-style) | Post-execution verifier | Si falla |
|---|---|---|---|
| system (volume/CPU/RAM/GPU) | rate-limit (max 1/sec) | re-leer y comparar con valor pedido (±5 %) | UNVERIFIED |
| apps (open) | resolver path universal | `psutil.process_iter()` ver pid > 0 dentro de 3 s | UNVERIFIED + propose retry |
| apps (close) | ya en config: confirmación destructiva | proceso desaparece de psutil en 5 s | "no respondió, sigues queriendo force-kill?" |
| files (write) | path dentro de sandbox roots | `os.path.exists` + `os.path.getsize > 0` + opcional `hashlib` | UNVERIFIED, no rollback automático |
| web | URL en allowlist o user-pasted | HTTP status 200 + content len | UNVERIFIED |
| terminal | regex bloqueo destructivos (rm -rf, format, reg delete...) | exit code + stderr capture | reportar exit-code, never claim success |
| GUI (UIA/AttachThreadInput) | window handle válido | UIA-tree query post-action: ¿elemento target en estado esperado?, o **frame buffer diff numpy** | UNVERIFIED + screenshot to user |
| media keys | siempre seguro | nada (fire-and-forget) | sin verifier |
| memory | filter PII (existing secret filter) | SQLite SELECT del row recién insertado | rollback insert |

**Pattern AEGIS** (arXiv 2603.12621): tres etapas — extract strings → content scan → policy. Carter ya tiene el secret-filter (etapa 1-2). Falta **etapa 3 = policy registry-driven** (sec. 15).

**Cuándo declarar UNVERIFIED:**
- 3 reintentos con mismos args fallaron.
- Verifier post-action no confirma estado esperado.
- Tool tardó >timeout (default 6 s).
- Excepción inesperada en tool body.

**No usar segundo LLM call** para verificar (literatura "self-consistency" añade 1-3 s, no costeable). El verifier es código determinístico.

### 7. Anti fake-success estructural

**El patrón ganador (validado en Cline, derivado de papers arXiv 2412.04141 y survey 2509.18970):**

```python
# pseudo
def reply_post_filter(model_response: str, trace: ToolTrace) -> str:
    claims_success = HONEST_DETECTOR.has_success_claim(model_response)  # 13 detectores existentes
    has_successful_tool = trace.has_any_tool_with_ok_true()
    if claims_success and not has_successful_tool:
        return rewrite_to_unverified(model_response, trace)   # NO re-prompt
    return model_response
```

**Reglas duras:**
1. **Reply rewriting, no re-prompt.** Re-prompt fue probado y "confunde el modelo" (tu propio reporte). El paper Apple "draft-conditioned constrained decoding" (arXiv 2603.03305) confirma que post-edit > regenerate para correctness.
2. **Constrained generation gate**: si trace está vacío y el usuario pidió acción explícita (heurística: verbos "abrí, cerrá, subí, busquemos"), **forzar al modelo en el siguiente turno** con grammar que requiere `<tool_call>` antes de cualquier afirmación.
3. **Trazas inmutables** (Ed25519 signing al estilo AEGIS): el verifier no puede ser eludido por instrucciones del modelo en thinking.
4. **Cero latencia añadida**: el detector son regex + estado SQLite, ~1-3 ms.

### 8. Memoria — persistencia y recall

| Stack | Overhead RAM | Latencia search | Setup | Multi-tenant | Recomendación Carter |
|---|---|---|---|---|---|
| **SQLite + sqlite-vec + bge-small CPU** | 100 MB | 5-30 ms | trivial | no necesario | ✅ **ELEGIDO** |
| ChromaDB embedded | 200-500 MB (Python in-process, comparte GIL) | 10-50 ms | trivial | medio | viable, pero peor en ≤8 GB |
| Qdrant local (proceso aparte) | 200 MB | 5-15 ms | docker | sí | overkill local-only |
| FAISS | 100 MB | <5 ms | requiere code | no | sin metadata, descartado |
| MemGPT/Letta runtime | 1-2 GB extra | 50-200 ms | complejo | sí | overkill |
| mem0 SDK | 100-300 MB | depende | trivial | sí | viable si se quiere arch hierarchy |

**Embeddings recomendados (CPU):**
- `intfloat/multilingual-e5-small` (118 M params, 384-dim, ~30 ms/query, **ES-nativo**).
- `bge-m3` para multilingüe + dense+sparse (más caro, 568 M params).
- `jina-embeddings-v3` también aceptable.

**Esquema SQLite:**
```sql
CREATE TABLE memories(
  id INTEGER PRIMARY KEY,
  ts INTEGER, role TEXT, scope TEXT,   -- 'user_pref', 'episodic', 'fact'
  content TEXT, content_hash TEXT,
  embedding BLOB,                       -- sqlite-vec virtual table o BLOB float32
  ttl INTEGER, consent_ts INTEGER,
  pii_flags TEXT
);
CREATE VIRTUAL TABLE vec_idx USING vec0(embedding float[384]);
```

**Forgetting policy:** ttl basado en `scope`:
- `user_pref` → permanente.
- `episodic` → 30 días + decay log scoring.
- `fact` corroborado N≥2 veces → permanente; sino 7 días.

**LoCoMo benchmark insight** (Letta blog, abr 2026): un agente con `search_files` + `answer_question` sobre filesystem alcanzó 74 % vs Mem0 graph 68.5 %. **Implicación para Carter:** no sobre-ingeniar memoria; SQL+vec con 2 tools (`memory_search`, `memory_save`) basta.

### 9. Manejo de contexto y compaction

**Decisiones:**
- `num_ctx=8192` por defecto (no 32K ni 128K). Razón: KV-cache grow lineal, modelos ≤14 B degradan calidad >16K.
- **Compaction al 70 %** del num_ctx (~5700 tok): el último N=4 turnos quedan crudos, lo previo se resume con el mismo modelo en una llamada off-budget.
- **Prefix caching** de Ollama: mantener `keep_alive: -1` en producción (modelo siempre residente), system prompt + tool catalog estables byte-a-byte (sin timestamps dinámicos). Speedup confirmado 17.7x (962 ms → 54 ms en eval del prompt grande).
- `OLLAMA_KV_CACHE_TYPE=q8_0` + `OLLAMA_FLASH_ATTENTION=1`: reduce KV cache ~50 % sin degradación perceptible (smcleod.net 2024).
- Streaming de respuestas para feedback inmediato; el reply rewriter de §7 corre post-stream pero antes de "completed".
- JetBrains 2025 "efficient context" lesson: priorizar últimos 3-5 turnos completos > resumen comprimido global.

### 10. Tools — construcción óptima

**Granularidad:** **fina (~33-50 tools), no gruesa.** Datos:
- MCP ecosystem (1700+ servers, sec 2025) prueba que tools chicas con schema estricto escalan mejor.
- Goose, Cline, OpenAI Assistants tools son finos.
- Tools gordos con sub-action enum (`app(action="open"|"close"|"list")`) **incrementan parse failures** ~6-10 % en modelos ≤8 B (errores en enum).

**Schema design — JSONSchema strict:**
- `additionalProperties: false`.
- enums siempre que el dominio sea cerrado.
- descriptions ≤100 caracteres (Hermes regurgitation).
- nombres lowercase_snake.
- agrupar similares por prefijo: `system_volume_set`, `system_cpu_get`, `app_open`, `app_close`.

**Errors:** `ok=False` (devuelto al modelo en `tool_response`) es preferible a `raise` porque permite al modelo reintentar con otros args. Salvo destructivo confirmado, donde `raise SafetyAbort` interrumpe loop.

**Idempotencia:** todas las tools `_get_*` son idempotentes; `_set_*` añaden `expected_state` arg opcional para verificación.

**Side-effect markers:** decorador `@destructive` que dispara confirmación.

**MCP compatibility:** estructurar tools de Carter como **MCP servers** futuros — aunque ahora corras todo in-process, escribir el wrapper FastMCP hace el sistema interoperable con Goose, Cline, Cursor sin reescribir lógica.

### 11. GUI control — apps CEF

**Estado del arte 2026:**

| Stack | Funciona en Steam/Discord/Spotify | Latencia | Robustez |
|---|---|---|---|
| pyautogui (SendInput) | ❌ apps in background | n/a | nula |
| WM_LBUTTONDOWN msg post | parcialmente | rápida | frágil |
| **AttachThreadInput + mouse_event coords absolutas** | ✅✅ confirmado | 50-200 ms | alta con re-attach |
| **UIA AutomationElement.Invoke()** | ✅ apps WPF/WinForms; ❌ CEF directo | 100-500 ms | alta |
| pywinauto backend=uia | ❌ CEF (issue #606) | media | media |
| Chrome `--force-renderer-accessibility` flag CEF | ⚠️ requiere relanzar app con flag | media | requiere user-cooperation |
| **OmniParser V2 (YOLOv8 + Florence-2) + VLM** | ✅ universal pero caro | **3-8 s** | media |
| ScreenSpot Pro VLM | 39.6 % accuracy | 5-15 s | baja |
| Set-of-Mark + qwen2.5-vl:7b | parcial | 4-10 s | media |

**Veredicto:** **mantener AttachThreadInput + UIA + frame-buffer numpy diff como verifier**, agregar **fallback OmniParser+qwen2.5-vl:3b solo en categoría "GUI"** y declararla **opt-in con presupuesto >8 s**, no <8s.

```python
# control universal:
if uia_element_found(target):
    invoke_uia_pattern(target)
elif app_is_cef(hwnd):
    attach_thread_input(target_thread, current_thread, True)
    SetForegroundWindow(hwnd); time.sleep(0.05)
    mouse_event_absolute(x, y); time.sleep(0.05)
    attach_thread_input(target_thread, current_thread, False)
    verify_via_numpy_frame_diff(before, after)
else:
    fallback_omniparser_vlm()  # rompe budget, pedirle al user paciencia
```

### 12. Visión — cuándo y cómo

| Backend | VRAM | Latencia screenshot+inferencia | OCR ES quality |
|---|---|---|---|
| mss (screenshot) | 0 | <50 ms | n/a (no inferencia) |
| DXGI desktop dup | 0 | <30 ms | n/a |
| **qwen2.5-vl:3b** | ~3 GB | 1.5-3 s/imagen | bueno |
| qwen2.5-vl:7b | ~6 GB | 2-5 s | excelente (51.6 OCRBench v2 con prompt absolute) |
| llava-llama3:8b | 5 GB | 2-4 s | medio |
| minicpm-v 2.6 (8B) | 5.5 GB | 1.5-3 s, OpenCompass 70.2 | bueno |
| Florence-2-large | 1 GB | <500 ms grounding | OCR limitado, mejor para detection |
| Tesseract | CPU | 200-500 ms | medio en ES, bueno con ajuste |
| PaddleOCR | CPU/GPU 1 GB | 100-300 ms | excelente ES |
| surya-ocr | 1 GB | 500-1000 ms | excelente multilingüe |

**Recomendación tier-aware:**
- 6-8 GB: **NO VLM residente.** Solo Tesseract / PaddleOCR CPU, llamado bajo demanda.
- 16 GB: qwen2.5-vl:3b residente + PaddleOCR fallback.
- 24 GB: qwen2.5-vl:7b residente + Florence-2 para grounding rápido.

**Estrategia:** UIA primero (free, <500 ms) → si no encuentra elemento → OCR (Paddle, 200 ms) → si OCR no resuelve → VLM (3-8 s) → user-loop si VLM también falla.

### 13. Multi-step missions

"Abrí Steam y andá a biblioteca y buscá Batman":

**Patrón Plan-and-Execute light** (NO ReWOO porque tools dependen de estados anteriores):
1. Detectar misión (heurística: ≥2 verbos imperativos coordinados o keyword "y luego").
2. **Single LLM call al planner** que devuelve lista de pasos con tool stubs (no args). Usar mismo modelo, pero con system prompt "Planner-mode: outline tools sequence".
3. Ejecutar cada paso vía ReAct loop normal.
4. **Checkpoints**: snapshot de estado del SO (procesos abiertos, foco) antes de cada paso destructivo.
5. **Rollback**: si paso N falla, devolver estado a paso N-1 (cerrar app abierta, etc.). Solo destructivos elegibles.
6. **Progress reporting**: mensaje "Paso X/Y: …" cada paso (UX Cursor Composer).
7. **Cleanup automático**: si misión aborta, cerrar lo que abriste.

Cómo lo hacen los referentes:
- **Devin**: planner de alto nivel + workers que escriben código + diff-based rollback.
- **Aider multi-file**: editor diff-tracked + git auto-commits para rollback.
- **Cursor Composer**: planner + per-file executor + revert button.

Carter v4 puede empezar simple: planner como **un único LLM call extra al inicio de la misión**, máximo 8 pasos, sin re-planning intermedio (lo agrega complejidad y latencia). Si paso falla 2x → abortar misión, no replan.

### 14. Voz (Fase 2)

| ASR | RTFx | WER | VRAM | Streaming | ES |
|---|---|---|---|---|---|
| **whisper.cpp small** | 5-10x | 8-12 % | 500 MB | manual chunking | ✅ |
| **faster-whisper small int8** | 12-20x | 8-12 % | 500 MB | manual | ✅ ⭐ |
| **distil-whisper-large-v3** | 6x más rápido que large-v3, 1-2 % WER gap | 9-13 % | 2 GB | manual | parcial |
| **NVIDIA Parakeet TDT 0.6B v2** | ~2000 RTFx | 5-7 % | 2 GB | nativo, 80-1120 ms latencia ajustable | ❌ inglés/europeo |
| Parakeet.cpp Nemotron 600M | streaming nativo | 8-10 % | 800 MB | 80 ms | ❌ ES limitado |
| Canary Qwen 2.5B | 88 RTFx | **5.63 %** | 8 GB | streaming 2.5 s | parcial |

**Recomendación voz fase 2:**
- ASR: **`faster-whisper small` int8 (CPU+GPU mix)**, ES nativo, <500 ms para 5 s de audio.
- Wakeword: **openWakeWord** (open source, ONNX) **o Picovoice Porcupine** (custom wake word "Carter" en 10 s, mejor FRR/FAR pero requiere AccessKey).
- VAD: silero-vad (ya estándar industria).

| TTS | Latencia (200 chars) | Calidad | VRAM | ES |
|---|---|---|---|---|
| **Piper** | 100-300 ms | aceptable | CPU | ✅ varias voces es-ES |
| **Kokoro 82M** | <300 ms | buena | 200 MB | parcial (ES roadmap) |
| Coqui XTTS-v2 | 1-2 s | excelente, voice cloning | 2 GB | ✅✅ |
| OpenAudio S1 | 500 ms | excelente | 2 GB | ✅ multilingüe |
| F5-TTS | 5-7 s | excelente | 2 GB | parcial |

**Recomendación TTS:** **Piper** (latencia bajísima, ES estable) por defecto; **XTTS-v2** opcional cuando user pida voz personalizada.

**Latencia E2E objetivo voz fase 2:** wakeword <500 ms + ASR streaming first-token <800 ms + LLM tool turn 1-2 s + TTS first-chunk <300 ms = **<3 s perceptual**, total task <8 s mantenido.

### 15. Seguridad y safety

**Patrón híbrido AEGIS + AgentSpec + Goose permission scopes:**

1. **Pre-execution firewall (AEGIS)** — middleware antes de ejecutar cualquier tool:
   - Extracción profunda de strings (args anidados).
   - Risk scan: regex destructivos, paths fuera de sandbox, comandos shell prohibidos.
   - Policy validation: registry-driven (tabla SQL `policies(tool_name, args_pattern, action)`).
   - Output: `allow | block | pending(human)` — overhead <10 ms (paper midió 8.3 ms median).

2. **Permission scopes (Goose model):** AllowOnce / AlwaysAllow (per session) / AlwaysAllowGlobal (persistido) / Deny / DenyForever. Persistir en SQLite.

3. **Sandbox FS**: roots configurables (`%USERPROFILE%/Carter`, `%USERPROFILE%/Documents`, etc.); `pathlib.Path.resolve()` chequea que no escapa con `..`.

4. **Sandbox terminal**: subprocess con env limpio, working dir dentro del sandbox, timeout 30 s, allowlist binarios (no `cmd /c`, `powershell -enc`, `reg`, `format`, `diskpart`, `bcdedit`, `wmic`).

5. **AgentSpec rules** (DSL para reglas runtime, ICSE'26): definir reglas declarativas para destructivos, ej:
   ```
   rule delete_files: trigger=tool_call(name="files_delete")
   predicates: count(targets) > 5 OR any(target.ext in [".exe", ".dll"])
   enforcement: user_inspection
   ```
   AgentSpec reportó >90 % unsafe-execution prevention en code-agent eval.

6. **Capability-based**: cada sesión tiene un `Capabilities` token con scopes activos; tools solicitan scope, si no, bloqueo.

7. **Confirmación crítica patterns:** "Vas a [acción] sobre [target]. ¿Confirmás? (sí/no)". Timeout 30 s = no.

### 16. Testing y validación

**Matriz 18×30=540 robusta:**

- **Mock mode**: tools devuelven `ok=True` con resultados sintéticos. Testea loop, parser, prompts.
- **Live-safe**: tools reales pero con sandbox-only, **sin** terminal destructivo, sin `app_close` real (mock-only la última).
- **Live-real**: full pipeline, sólo en máquina de test dedicada.

**Pattern:**
```
for category in 18: for case in 30:
  expected = case.expected_outcome
  actual = run_carter(case.input, mode="mock"|"live_safe"|"live_real")
  pass = verifier_strict(actual, expected)
```

**Verificadores estrictos**:
- Categorías chat/identidad/conocimiento/memoria → text-similarity + auditor 13 detectors.
- Categorías system/apps/files/web → return-state assertion (proceso vivo, archivo existe, etc.).
- GUI → screenshot diff + UIA tree post-state.

**Regression test pattern (paper arXiv 2511.17330 "Agentic Verification"):** snapshot trace baseline, comparar deltas en cada PR. Si BFCL drop >2 % → revert.

**Benchmarks externos para regression macro:**
- **AgentBench** (sub-tasks: web, OS, db).
- **OSWorld**: 369 tasks Linux+Win.
- **WindowsAgentArena (arXiv 2409.08264)**: 150+ Windows tasks, baseline humano 74.5 %, agentes top 19.5 %. **Carter es competitivo si supera 25 % en WAA-Lite subset**.
- **τ-bench / TauBench**: agentic conversation success rate.

### 17. Stack arquitectural recomendado completo (resumen ejecutivo)

| Componente | Decisión |
|---|---|
| **Loop** | ReAct single-thread tipo "nO" (Claude Code), max 3 reintentos, compaction 70 % |
| **Modelo default 6 GB** | qwen3:4b-instruct-2507 Q4_K_M |
| **Modelo default 8 GB** | granite4.1:8b-instruct (conservador) o qwen3:8b-instruct-2507 (agresivo) |
| **Modelo default 16 GB** | qwen3:14b-instruct-2507 |
| **Modelo default 24 GB** | qwen3:30b-a3b-instruct-2507 (MoE) |
| **Multi-modelo** | NO. Único modelo + pre-LLM rule router |
| **Function calling format** | Hermes XML `<tool_call>` + JSON Schema enforcement opcional |
| **System prompt** | ~600 tok: identidad + contract + idioma + destruct + tools dinámicas |
| **Verifier** | Inline determinístico, NO segundo LLM call |
| **Anti fake-success** | Reply rewriting (no re-prompt) + grammar gate condicional |
| **Memory** | SQLite + sqlite-vec + multilingual-e5-small CPU |
| **Embedding** | intfloat/multilingual-e5-small (384-dim, ES) |
| **Context** | num_ctx=8192, prefix cache estable, KV q8_0, FlashAttn=1 |
| **Multi-step** | Planner LLM call único → ReAct executor con checkpoints |
| **GUI** | UIA primero, AttachThreadInput+mouse_event para CEF, frame-diff verifier |
| **Vision** | tier-aware: 6-8 GB ninguno, 16 GB qwen2.5-vl:3b on-demand, 24 GB :7b residente |
| **Voice (fase 2)** | faster-whisper small + Piper + openWakeWord + silero-vad |
| **Tools count** | 33-50, granularidad fina, JSONSchema strict, MCP-ready |
| **Safety** | AEGIS firewall + AgentSpec rules + Goose-style scopes + capability tokens |

### 18. Gap Analysis vs Carter v4 actual

**P0 — Críticos para 540/540 PASS REAL:**
1. **Cambiar modelo default qwen3:8b → qwen3:4b-instruct-2507 (no-thinking).** Archivo: config/llm.toml o equiv. Esfuerzo: 1 día (incl. retest 540). Impacto: latencia 7-21 s → 0.5-2 s, BFCL similar o mejor. Justificación: tu propio dato C04 (qwen3:8b rompe Alexa) + thinking-mode latencia ~10-20 s confirmada en literatura.
2. **Reply rewriting honest-by-construction.** Archivo: `loop/post_filter.py` nuevo. Esfuerzo: 2 días. Impacto: elimina restantes fake-success que el Auditor detecta pero no repara. Justificación: §7, papers arXiv 2412.04141, 2509.18970.
3. **AEGIS pre-execution firewall.** Archivo: `safety/firewall.py`. Esfuerzo: 3 días. Impacto: bloquea destructivos antes de side-effect, base para AgentSpec rules. Justificación: arXiv 2603.12621, latencia 8.3 ms.
4. **Verifier post-action por categoría.** Archivos: `tools/*/verifier.py`. Esfuerzo: 4 días (1 día por cluster system/apps/files/gui). Impacto: UNVERIFIED estructural en lugar de optimismo. Justificación: §6.
5. **JSON Schema enforcement opcional para tools destructivos.** Archivo: adapter Ollama. Esfuerzo: 1 día. Impacto: parse failure ~0 % en sandbox/terminal/files. Justificación: §4 + JSONSchemaBench (arXiv 2501.10868).

**P1 — Importantes:**
6. **Memory con sqlite-vec + multilingual-e5-small.** Archivo: `memory/store.py`. Esfuerzo: 2 días. Impacto: C04 26/30 → 30/30 esperable.
7. **MCP-style tool wrappers.** Esfuerzo: 3 días. Impacto: futureproof + composable.
8. **Multi-step planner light.** Esfuerzo: 3 días. Impacto: misiones compuestas pasan de hit-or-miss a determinísticas.
9. **AgentSpec rules DSL para destructivos.** Esfuerzo: 2 días. Impacto: governance auditable.
10. **Compaction al 70 % automático con resumen LLM.** Esfuerzo: 1 día. Impacto: sesiones largas dejan de degradar.

**P2 — Nice-to-have:**
11. Speculative decoding con qwen3:0.6b draft (solo 24 GB tier).
12. VLM fallback OmniParser+qwen2.5-vl:3b para GUI 16 GB+.
13. ASR/TTS fase 2 (faster-whisper + Piper).
14. Permission persistence "AlwaysAllow" estilo Goose.
15. Telemetría de regresión BFCL-mini interna (10-50 cases) en CI.

### 19. Roadmap sugerido (12 semanas)

**Semana 1 — Foundation modelo.**
- Cambio default a qwen3:4b-instruct-2507. Comando `ollama pull qwen3:4b-instruct-2507`.
- Re-baseline 540 con modelo nuevo.
- Criterio aceptación: latencia mediana ≤2 s en C01-C03; BFCL interno ≥66 %.

**Semana 2 — Honest-by-construction.**
- Implementar reply rewriting.
- Endurecer 13 detectors con corpus de "trampas anti-honest" del usuario.
- Criterio aceptación: cero falsos "lo hice" en 100 conversaciones de stress.

**Semana 3 — AEGIS firewall + AgentSpec base.**
- Middleware pre-execution con allow/block/pending.
- Registry-driven policies para terminal y filesystem.
- Criterio aceptación: 50 destructive prompts → 100 % bloqueados o pending; falsos positivos ≤2 %.

**Semana 4 — Verifiers post-action.**
- Verifier por cluster (system, apps, files, web, gui, memory).
- Criterio aceptación: UNVERIFIED en lugar de fake-success en 30 forced-failure cases.

**Semana 5-6 — Memory upgrade + multi-step.**
- sqlite-vec + multilingual-e5-small.
- Planner light para misiones.
- Criterio aceptación: C04 30/30; misión "abrí Steam→biblioteca→Batman" 8/10 successful + 2/10 UNVERIFIED honest.

**Semana 7 — Context y caching.**
- num_ctx tuning, prefix cache estable, KV q8_0, FlashAttn=1.
- Criterio aceptación: prompt eval cold→warm 17x speedup verificado.

**Semana 8 — Tools refactor a MCP-shape.**
- Wrappers JSONSchema strict.
- Criterio aceptación: 0 parse failures sobre 200 tool calls de eval.

**Semana 9-10 — GUI robustness.**
- AttachThreadInput + UIA + frame-diff verifier en Steam, Discord, Spotify, Slack.
- Criterio aceptación: ≥85 % success en 50 GUI cases reales; UNVERIFIED honesto en el resto.

**Semana 11 — Tier 16/24 GB experimentación.**
- qwen3:14b-instruct-2507, qwen3:30b-a3b-instruct-2507.
- VLM fallback opcional.
- Criterio aceptación: BFCL interno ≥73 % en tier 24 GB.

**Semana 12 — Hardening + 540 final.**
- Permission persistence.
- Telemetría regression CI.
- Final 540 PASS REAL run.
- Criterio aceptación: ≥510/540 (94.5 %) en 8 GB tier; ≥530/540 (98 %) en 24 GB tier.

### 20. Riesgos y trade-offs honestos

**Lo que NO se puede lograr con 8 GB y <8 s latencia:**

1. **540/540 PASS REAL en 8 GB tier no es realista.** Categoría GUI con apps CEF en estado raro (Steam minimizado tras login flow) requiere VLM, que rompe budget. Estimación honesta: **510-520/540 es el techo realista** en 8 GB con <8 s estricto.
2. **Misiones compuestas largas (≥6 pasos) en 8 GB** caen al borde del budget total acumulado. Cada step 1.5 s × 6 = 9 s ya pasa el hard-limit de 8 s percibido como "tarea". Mitigación: progress reporting incremental (UX), pero aún así >5 pasos no es "Alexa-fast".
3. **OCR/VLM para GUI fallback exige 16 GB+.** En 6-8 GB sólo cabe Tesseract/Paddle CPU; useful pero no resuelve casos donde target no tiene texto (ícono Steam Library tab).
4. **Multilingüe español de altísima calidad estilística** está en qwen3:14B+; en 4B la naturalidad ES es buena pero no excelente.
5. **Voz fase 2 con <500 ms wake-to-first-token + LLM <2 s** requiere modelo siempre residente (`keep_alive=-1`) → consume VRAM permanentemente. En 8 GB con qwen3:8b residente quedan ~1.5 GB libres, insuficientes para Whisper-large; obliga a `whisper-small` con WER ~12 % en español ruidoso.
6. **Compositional reasoning multi-tool (>3 tools encadenadas) sin thinking** es marginal en modelos 4B no-thinking. La variante 4B-Thinking-2507 da 71.2 BFCL pero a costa de latencia 5-15 s. Trade-off: para C04 memory y misiones, considerar **thinking on solo cuando heuristic detecta complejidad** (palabras clave: "y luego", "pero antes", "después de").
7. **xLAM, ToolACE, Hammer-7b**: aunque BFCL competitivos, **no son operacionales en Ollama** sin escribir custom Modelfile + parser; si el equipo migra a vLLM en el futuro, recuperan estas opciones, pero hoy son distracción.
8. **gpt-oss-20b** es viable en 16 GB (MXFP4 ~13 GB) pero requiere **Harmony chat format**, distinto del estándar OpenAI; integrarlo en adapter Ollama de Carter exige rework no trivial. Beneficio adicional vs qwen3:14b es marginal (BFCL 67 vs 74), no justifica.
9. **Hermes 4 14B / 4.3 36B** son interesantes pero introducen thinking mode opcional que complica el budget; **probar sólo después de baseline qwen3-Instruct-2507** estabilizado.
10. **Escenarios de adversarial prompt-injection** (paper MCP Safety Audit, arXiv 2504.03767) no se mitigan completamente con AEGIS — siguen exigiendo human-in-loop para destructivos. No prometer "100 % seguro".

**Decisiones que aceptan honestamente trade-offs:**
- Latencia <2 s en chat trivial > sofisticación arquitectural.
- Reply rewriting > re-prompt aunque suene "menos elegante" (no introduce loops).
- Single-model > router porque 8 GB no permite dos residentes.
- AttachThreadInput hack > buscar API limpia que no existe para CEF en 2026.
- Verifier inline determinístico > segundo LLM verifier (latencia inaceptable).
- num_ctx=8192 > 32K para preservar latencia.

**Si el usuario considera flexibilizar restricciones**, las palancas con mejor ROI:
- Subir hard-limit a 12 s para misiones compuestas (no chat trivial) → desbloquea 30+ casos.
- Aceptar 16 GB como tier objetivo → desbloquea VLM residente y qwen3:14b → +5-10 casos GUI.
- Permitir thinking mode condicional (heurística keyword) → +3-5 casos compositional pero rompe budget en esos casos específicos; trade explícito al usuario.

---

## Recommendations (concretas, escalonadas)

**Esta semana (acción inmediata):**
1. `ollama pull qwen3:4b-instruct-2507` y re-correr matriz 540 como nueva baseline. Si C01-C04 pasan con latencia <2 s → confirmado el cambio de default.
2. Implementar reply rewriting (P0 #2) — 2 días, máximo impacto sobre fake-success residuales.

**Próximas 2-3 semanas:**
3. AEGIS pre-execution firewall + AgentSpec rules para destructivos (P0 #3).
4. Verifiers post-action por cluster (P0 #4).

**Mes 2-3:**
5. Memory upgrade sqlite-vec (P1 #6) y multi-step planner (P1 #8).
6. GUI hardening + experimentación tier 16/24 GB.

**Benchmarks que disparan re-evaluación:**
- Si Granite 4.2 (esperado mid-2026 según patrón IBM) supera BFCL 75 % en 8B → reconsiderar conservador.
- Si Qwen publica `qwen3.5:7B-Instruct-2510` con BFCL >75 → upgrade.
- Si Ollama publica integración nativa MCP server-side → migrar tools a MCP wrappers.
- Si latencia residual sigue >3 s en C04 con qwen3:4b → considerar speculative decoding (sólo tier 24 GB) o LoRA fine-tune sobre memoria.

---

## Caveats

- **Fechas y números BFCL**: scores tomados de blogs/papers entre julio 2024 y abril 2026; el leaderboard oficial Berkeley se actualiza continuamente. Los scores 2507 (Qwen3 mid-2025 refresh) son auto-reportados por Qwen y replicados por terceros pero no todos están "verified" en BFCL oficial.
- **Granite 4.1 release** (29 abr 2026, fuente IBM) es muy reciente; el tag exacto en `ollama.com/library/granite4` podría llamarse `granite4.1` o seguir `granite4`; verificar antes del despliegue.
- **Latencias 4060/4090** son medianas de community benchmarks (Hardware Corner, llama.cpp Q4_K_XL @ 16K ctx); varían ±20 % según context length real, paralelismo, KV-cache config, driver CUDA.
- **WindowsAgentArena scores** (19.5 % top en paper original 2024) reflejan VLMs grandes con cloud; agentes locales tipo Carter probablemente más bajos en absolute, **pero el set de tareas WAA es mucho más amplio que las 540 de Carter**, no comparable directo.
- **Ollama "tools" tag inconsistencia** (issue #12286): algunos modelos figuran con tag tools en registry pero responden 400 al request. Validar empíricamente con curl antes de comprometer modelo.
- **xLAM 88.24 BFCL** es del leaderboard v1 (julio 2024), no v3 multi-turn; comparaciones cross-version son inválidas estrictamente.
- **OmniParser V2 ScreenSpot Pro 39.6 %** es el state-of-the-art a fecha de los blogs consultados (feb 2025); puede haber mejoras posteriores.
- **Hermes 4 / 4.3** existe en HF pero **no como tag oficial Ollama** — recomendación los marca como "comunidad GGUF" lo cual implica Modelfile custom + posibles bugs parser.
- **mem0 vs Letta benchmark dispute** (LoCoMo): cada team reporta números diferentes; usar 74 % filesystem-only de Letta como baseline conservador.
- **AEGIS, AgentSpec arxiv IDs** están en preprints aún sin replicación independiente extensiva; los números (8.3 ms latency, 90 % blocking) son del paper, ojo en producción.
- **gpt-oss tools requiere Harmony format**, no comprobado pero literatura sugiere que necesita parser específico no provisto por Ollama nativo en todos los releases.
- **Predicciones de roadmap (semanas 1-12)** asumen developer senior a tiempo completo; ajustar según capacidad real.
- **Ningún sistema local-only es 100 % seguro** contra prompt-injection en contenido externo (web, docs, paths del usuario). AEGIS+AgentSpec mitigan, no eliminan.