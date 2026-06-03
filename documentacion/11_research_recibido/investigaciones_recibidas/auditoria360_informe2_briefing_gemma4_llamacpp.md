# Briefing técnico: Gemma 4 E4B-it Q4_K_M en llama.cpp (build b9090, ~6 GB VRAM)

**TL;DR**
- Gemma 4 fue anunciada por Google DeepMind el **2 de abril de 2026** bajo licencia Apache 2.0, con cuatro variantes (E2B, E4B, 26B A4B MoE, 31B Dense); el perfil del usuario ("E4B-it Q4_K_M, monoslot, ~6 GB VRAM") es **viable** con llama.cpp b9090, pero con caveats importantes en SWA, mmproj, tool-calling y especulativo.
- **Decodificación especulativa con el drafter oficial (`Gemma4AssistantForCausalLM`) NO está soportada en mainline `ggml-org/llama.cpp` en b9090** — sólo en forks (ik_llama.cpp PR #1744 mergeada el 10/05/2026, AtomicChat `atomic-llama-cpp-turboquant`, y un fork personal `reffdev/llama.cpp/tree/gemma4-mtp` que en E4B reporta 70–87 % de aceptación y hasta +60 % de throughput según el comentario de su autor en la Discussion #22735). En 6 GB VRAM no es viable añadir un draft model en paralelo a E4B-Q4 + mmproj.
- En E4B, el modo *thinking* y el tool-calling existen pero son **frágiles**: gemma4-ai.com (basado en r/LocalLLaMA, abril 2026) midió ~15 % de errores de formato en function-calling para **Gemma 4 31B** Q4_K_M (no E4B), y E4B es explícitamente "much weaker at tool calling than 26B" según el gist de Daniel Farina ("opencode-gemma4-ollama-macos.md", probado en MacBook M1 Max 32 GB el 2-Abr-2026). Conviene constraint con GBNF + `--jinja` y un grammar específico para la notación `fc` de Gemma.

---

## 1) Release y variantes — CONFIRMADO

**Fecha de release**: 2 de abril de 2026 (Google DeepMind blog, "Gemma 4: Byte for byte, the most capable open models"; también ai.google.dev/gemma/docs/releases). Wikipedia recoge la misma fecha. Algunas notas de prensa secundarias citan 31 de marzo de 2026 (aurigait.com), conflicto menor — fuente primaria de Google manda: **2-Abr-2026**.

**Variantes oficiales (4)** — ai.google.dev/gemma/docs/core, huggingface.co/google/gemma-4-E4B, deepmind.google/models/gemma/gemma-4/:
- **E2B**: dense con Per-Layer Embeddings (PLE), ~2.3 B parámetros efectivos / ~5.1 B totales (incluyendo PLE).
- **E4B**: dense con PLE, **~4.5 B parámetros efectivos / ~8 B totales incluyendo embeddings** (llm-stats.com confirma "8.0 billion parameters"; Medium/Datature: ~4.5 B effective, 42 capas, 128K contexto).
- **26B A4B**: **MoE con 128 expertos finos, top-8 routing**, 25.2 B totales / **3.8 B activos por token** (la "A4B" = ~4B "active"). Esta es la "MoE más grande" — confirma el comentario del usuario sobre "perfiles MoE vram12/16".
- **31B Dense**: 30.7 B parámetros, 60 capas, 256K contexto.

**Variante "E"**: el "E" es "Effective" (no "Edge"); usa **Per-Layer Embeddings (PLE)** — cada capa tiene su propio embedding pequeño por token, almacenado en RAM y consultado vía lookup. Esto explica por qué el "modelo de 4B efectivo" pesa ~8 B en memoria estática. Es la evolución de la idea de Gemma 3n (que ya tenía E2B/E4B con MatFormer/PLE); en Gemma 4 se mantiene PLE pero el resto de la arquitectura es nuevo y la familia E va alineada con la familia mayor.

**Licencia**: Apache 2.0 (sin restricciones MAU, sin AUP), confirmado por blog.google y el model card oficial.

---

## 2) Arquitectura relevante para inferencia — CONFIRMADO

**Contexto**:
- E2B / **E4B: 128K tokens** (model card oficial).
- 26B A4B / 31B: 256K tokens.

**Atención híbrida (interleaved SWA + global)** — ai.google.dev/gemma/docs/core/model_card_4 (verbatim): "*The models employ a hybrid attention mechanism that interleaves local sliding window attention with full global attention, ensuring the final layer is always global.*"
- E2B/E4B: **ventana SWA = 512 tokens** (Maarten Grootendorst, "A Visual Guide to Gemma 4").
- 26B A4B/31B: ventana SWA = 1024 tokens.
- 5× sliding_attention seguidas de 1× full_attention, repetidas → ~50 capas SWA / 10 globales en los modelos grandes (issue #1607 ik_llama.cpp).
- Capas globales usan **Unified Keys & Values + Proportional RoPE (p-RoPE)** para reducir KV-cache en contextos largos.

**KV-cache**:
- Las capas SWA usan KV de tamaño ventana (no full-context) cuando se trata correctamente.
- **Crítico para el usuario**: el flag `--swa-full` **fuerza atención completa en todas las capas y rompe la economía de la iSWA**. njannasch.dev (verbatim): "*The critical mistake is adding --swa-full, which forces full attention on all layers and OOMs at high context.*" → **El usuario debe quitar `--swa-full`** del lanzamiento de llama-server salvo que tenga una razón muy específica (p.ej., workaround de bug). La recomendación es dejar que iSWA funcione con su cache compacto.
- `--kv-unified` y `-fa 1` (flash attention) son los flags correctos para SWA en Gemma 4.
- Para mono-usuario, `-np 1` reduce el SWA cache ~3× (aiproductivity.ai).

**Multimodal**:
- E2B/E4B: texto + imagen (resoluciones variables) + **audio nativo** (encoder Conformer estilo USM, hasta 30 s).
- 26B/31B: texto + imagen + video (frames hasta 60 s @ 1 fps).
- En llama.cpp el archivo `mmproj` es **separado**; para E4B-it, `mmproj-F16.gguf` ≈ **990 MB** (unsloth/gemma-4-E4B-it-GGUF, archivo verificado 990 MB exactos, SHA256 ddf46c21d7…). El mmproj contiene **ambos** encoders (visión + audio) en 1411 tensores. Audio en llama.cpp está aún en **estado experimental** y hay assert errors abiertos (issue #21816).

**Function calling**: nativo, con tokens especiales propios de Gemma 4. Soporta JSON schema y funciones Python (auto-conversión vía type hints / docstrings Google style). La notación "fc" de Gemma **no es JSON puro**: el parser de tool-calls en llama.cpp se invoca como `Chat format: peg-gemma4` (issue #21384).

**System prompt nativo**: Gemma 4 introduce soporte built-in para el rol `system` (cambio respecto a Gemma 3).

**Modo thinking**: tokens de control `<|think|>` (al inicio del system prompt) y delimitadores `<|channel|>thought\n...<channel|>`. **En E2B/E4B, si thinking está desactivado, el modelo NO emite tags vacíos** (a diferencia de los grandes 26B/31B), simplemente genera la respuesta final directamente.

---

## 3) Soporte en llama.cpp — CONFIRMADO (con bugs)

**Build b9090 fue publicado el 9 de mayo de 2026 a las 12:45 UTC**, commit 5757c4d ("cmake : update BoringSSL to 0.20260508.0 #22839") — github.com/ggml-org/llama.cpp/releases/tag/b9090. Es un release menor (bump de BoringSSL); el soporte de Gemma 4 viene de mergeos anteriores (alrededor de b8650–b8800 según los reports de bugs).

**Gemma 4 (E2B/E4B/26B/31B) están soportados en mainline** desde el lanzamiento día-0 (huggingface.co/blog/gemma4 lo confirma: "*day-0 support for many open-source inference engines*"). Los GGUFs oficiales están en `ggml-org/gemma-4-E4B-it-GGUF` y `unsloth/gemma-4-E4B-it-GGUF`.

**Q4_K_M para E4B**: bartowski/google_gemma-4-E4B-it-GGUF → archivo **Q4_K_M = ~5.41 GB**. Unsloth da un budget 4-bit de **5.5–6 GB** total (modelo + activación, sin mmproj). Esto significa que con **6 GB VRAM** ya estás al límite: 5.41 GB peso + ~0.4–0.6 GB KV cache a 8K ctx → ~6 GB **antes** de añadir el mmproj de 990 MB. Si se quiere visión/audio en el mismo GPU, **es necesario quantizar el mmproj a Q8 o forzar parte de los layers a CPU** (`-ngl` parcial), o renunciar al mmproj.

**Bugs conocidos relevantes para tu auditoría**:
1. **Tensor shape mismatch al cargar Gemma 4** (issue #21434): el campo `gemma4.attention.sliding_window_pattern` se guarda como `bool[]` en el GGUF pero llama.cpp lo lee como `uint32_t[]`, produciendo `is_swa()` incorrectos. **Fixed** en builds posteriores a b8660; en b9090 ya debería estar resuelto, pero conviene verificar log de carga (`print_info: n_embd_k_gqa`) para ver que los valores de las capas SWA/globales son consistentes.
2. **Cache reuse no soportado con `-fa` + `--swa-full`** (issue #21468): el cache reuse / prefix matching falla por la arquitectura de KV compartido entre capas — esto añade 60-90 s de TTFT con prompts grandes (p.ej. Claude Code system prompt). Otra razón para **no usar `--swa-full`**.
3. **Audio assert error en E4B** (issue #21816, build 8766): `GGML_ASSERT((cparams.causal_attn || cparams.n_ubatch >= n_tokens_all) ...)` falla en RTX 3060 12 GB al procesar audio. Si la auditoría incluye entrada de voz por el mmproj, hay riesgo de crash.
4. **`--json-schema` falla en sampler init para Gemma 4 E2B/E4B** (issue #22396, b8920): la ruta JSON-Schema → grammar lanza `std::exception`. **Workaround**: usar **`--grammar-file` con GBNF escrito a mano** en lugar de `--json-schema`.
5. **Tool-call array params se serializan como string JSON anidado** cuando el contenido contiene `{` o `}` (issue #21384, b8653/b8656). El parser PEG `peg-gemma4` aún tiene este bug; afecta funciones con arrays de objetos como argumentos.

**`--swa-full` veredicto explícito**: **QUITAR** del lanzamiento. Confirmado por njannasch.dev y issue #21468.

---

## 4) Decodificación especulativa — NO VIABLE en este perfil

**Familia de drafters MTP oficiales** (blog.google/innovation-and-ai/.../multi-token-prediction-gemma-4 — anuncio independiente de los modelos base):
- `google/gemma-4-E2B-it-assistant`
- `google/gemma-4-E4B-it-assistant` — **~78.8 M params (cifra autoritativa según el model card de AtomicChat/gemma-4-E4B-it-assistant-GGUF, verbatim: "Approximate size: 78.8M (assistant) / 8B target")**. La cifra de 156 M citada en Medium/kuldeepjadeja7 no está respaldada por el HF card primario.
- `google/gemma-4-26B-A4B-it-assistant`
- `google/gemma-4-31B-it-assistant` (~930 MB; Q8_0 ~510 MB).

Estos drafters usan una arquitectura propia `Gemma4AssistantForCausalLM` (en GGUF: `gemma4_assistant`) y comparten KV-cache con el modelo target. Para E2B/E4B usan **centroids masking** (compresión del lm_head sobre 262K vocabulario a ~4K candidatos vía 2048 centroides) — reduce el cómputo del lm_head ~45×.

**Estado en llama.cpp mainline a b9090**: **NO soportado**. Hallazgos:
- **Discussion #22735** ("Support Request for Gemma4AssistantForCausalLM") abierta 6-May-2026, **sin respuesta de mantenedores, sin merge**. En esa misma discussion, el usuario `reffdev` aporta el único punto de medición pública en E4B con MTP, verbatim: "*I have a fork with working Gemma 4 MTP speculative decoding (tested on E4B, ~70-87% acceptance depending on content, up to ~60% throughput improvement). Not PR-quality but functional.*"
- **PR #22673** ("llama + spec: MTP Support" por am17an), abierta 4-May-2026, **draft, no mergeada**, y cubre Qwen 3.6, **no Gemma 4** (override_arch = `qwen35_mtp`).
- AtomicChat HF card (verbatim): "*These GGUFs use the custom gemma4_assistant architecture and will not load in stock llama.cpp. ... Loading these files in upstream ggml-org/llama.cpp will fail with an unknown architecture error.*"
- Soporte funcional sólo en **forks**:
  - `ik_llama.cpp` PR #1744 (mergeada 10-May-2026); harness reproducible (karany97/llamacpp-gemma4-mtp) reporta **2.6–2.98× lossless speedup** verificado (Gemma 4 31B Q4_K_M target + 510 MB Q8_0 drafter: 7.05 → 21.02 t/s en EPYC 9655; 21.7 → 56.1 t/s en CPU + RTX 3090 con `--draft-max 3`, 85.2 % aceptación).
  - `atomic-llama-cpp-turboquant`: en su README reporta +30–50 % de throughput de prompts cortos en **26B A4B / 31B** dense (con f16 KV) y ~85–88 % de aceptación; **no en E4B**.
  - Fork personal `reffdev/llama.cpp/tree/gemma4-mtp`: el único con resultados específicos en **E4B** (70–87 % acept, +60 % throughput).
- vLLM tiene PR oficial (#41745 por ingeniero de Google) y `--speculative_config` ya funcional.

**Speculative con `--model-draft` usando E2B como draft de E4B** en stock llama.cpp: técnicamente posible (E2B GGUF Q4_K_M cabe en pocos GB), pero:
- **No cabe junto a E4B-Q4 + mmproj en 6 GB**: E2B-Q4 ≈ 4 GB (budget Unsloth) + E4B-Q4 ≈ 5.4 GB + mmproj 0.99 GB + 2× KV-cache → **≥10 GB**, fuera del presupuesto.
- Sin entrenamiento conjunto, la tasa de aceptación es baja → en sistemas pequeños el especulativo **resulta más lento** que el decode normal. Verbatim Dampfinchen en PR #22673: "*Right now on my system (6 GB VRAM, 32 GB RAM), speculative decoding just makes things much slower even on very small draft models because of that exact reason, they need own context and kv-cache.*"

**Veredicto para "vram4" (6 GB)**: **NO usar `--model-draft` ni `--draft`**. Esperar a soporte upstream del drafter MTP oficial (no presente en b9090) o, si se quisiera el speedup MTP de 2.5–3× ya disponible, mover a un fork (ik_llama.cpp) **y** subir a ≥12 GB VRAM. Para 6 GB, la decisión correcta es **dejar E4B-Q4_K_M monoslot sin draft**.

---

## 5) Tool-calling y multi-step — CONFIRMADO con caveats serios

**Native function calling**: sí, parte oficial del modelo (vía `apply_chat_template(..., tools=[...])`).

**Benchmarks oficiales (model card)**:
- τ²-bench (agentic tool use): **31B = 86.4 %**, **26B A4B = ~82 %**, **Gemma 3 27B = 6.6 %** — salto enorme respecto a Gemma 3.
- Para E4B no hay número público en τ²-bench en el material que pude encontrar; la inferencia es que es significativamente peor que los grandes.

**Benchmarks independientes para E4B**:
- aiexplr.com (Enterprise Benchmark Showdown, Apple Silicon MPS, abril 2026): E4B obtiene **100 % parse success / 90 % schema compliance** en structured JSON output, pero **multi-turn conversation falla al 0 %**; recomendación textual: "*Deploy as a specialist, not a general assistant.*"
- gemma4-ai.com/blog/gemma4-4bit-quantization (Abr 2026, basado en r/LocalLLaMA): "*Community testing on Reddit's r/LocalLLaMA reports roughly 15% format error rates for Gemma 4 31B function calling at 4-bit.*" → **esta cifra es para 31B, no E4B**; el caso 4-bit de E4B no tiene benchmark público, pero al ser un modelo menor se espera tasa ≥ esa.
- gist de **Daniel Farina, "opencode-gemma4-ollama-macos.md"** (gist.github.com/daniel-farina/87dc1c394b94e45bb700d27e9ea03193, última actividad 6-Abr-2026, probado en MacBook M1 Max 32 GB el 2-Abr-2026), verbatim en el bloque de comando llama-server: "*Note: E4B is much weaker at tool calling than 26B.*"
- MindStudio: "*E4B is more reliable on complex schemas. E2B performs well when the schema is straightforward... A good rule of thumb: if you have more than 10 functions in your schema, or if users are unlikely to phrase requests clearly, start with E4B.*"

**Conclusión para el voice assistant**: E4B-Q4_K_M es **utilizable para tool-calling si el esquema es simple y las funciones están bien descritas, pero NO fiable para chaining multi-paso ni multi-turno**. Recomendación: limitar a ≤10 herramientas, descripciones cortas y distintivas, y validar estrictamente las respuestas.

**GBNF / constrained decoding en llama.cpp para Gemma 4**:
- `--jinja` activa la plantilla de chat correcta y el parser `peg-gemma4` para tool_calls; **es necesario** para que `tool_calls` aparezca en `choices[].message.tool_calls`.
- **Importante** (discussion #21839): "*Most models use GBNF grammar to ensure proper tool calls. Gemma 4 only forces the structure, not the arguments. This is because common/json-schema-to-grammar.cpp only produces rules for JSON and not Gemma's fc notation.*" → el grammar built-in de llama.cpp constraint la **estructura** del tool-call pero **no los tipos de los argumentos**, por lo que el modelo puede aún alucinar argumentos inválidos.
- **Workaround práctico**: escribir GBNF manual que incluya tanto el wrapper `<|fc|>...` como la estructura JSON del schema, o usar LLGuidance (`--grammar-llg`, mergeada en PR #10224).
- **No mezclar `--json-schema` con E4B** (issue #22396): crashea el sampler. Usar `--grammar-file <archivo.gbnf>`.

**Alucinación de tools inexistentes**: no hay benchmark numérico explícito en las fuentes; comunidad reporta que es mitigable con (a) `tool_choice: "required"`, (b) GBNF constraint que enumere los `name` válidos como literal alternation, (c) lista de tools en system prompt repetida explícitamente.

---

## 6) Modo reasoning / thinking — CONFIRMADO

- **Toggle**: activar añadiendo `<|think|>` al **inicio del system prompt**; desactivar = quitar el token. ai.google.dev/gemma/docs/core/model_card_4.
- En E2B/E4B con thinking off, el modelo **no genera tags vacíos** (sí lo hacen 26B/31B).
- Impacto en latencia: el thinking emite tokens internos `<|channel|>thought\n...<channel|>[respuesta final]` que **se cuentan en el decode** y, por tanto, **añaden latencia** proporcional a la longitud del pensamiento. Para un asistente de voz local con presupuesto de latencia ajustado, **se recomienda DESACTIVAR thinking** salvo para queries complejas.
- Impacto en tool-calling: thinking activado tiende a mejorar planning multi-paso (en los modelos grandes); en E4B no hay evidencia clara de mejora y el costo de latencia es significativo. **Para tool-calling de un solo paso en E4B-Q4_K_M, desactivar thinking**.
- Historial: "*In multi-turn conversations, the historical model output should only include the final response. Thoughts from previous model turns must not be added before the next user turn begins.*" — importante para no contaminar el contexto.

---

## 7) Decode latency / tokens-per-second — DATOS LIMITADOS para 6 GB NVIDIA

**Benchmarks publicados que sí se pudieron localizar**:
- **InfoWorld (Serdar Yegulalp, Abr 2026)**, LM Studio Community E4B (Q4) + AMD Ryzen 5 3600 + **RTX 5060 8 GB**, 42/42 layers en GPU, 16K ctx: **72 tokens/sec decode**. Versión Unsloth (~4.84 GB) "*about as performant and useful*".
- **Anass Kartit (kartit.net, Abr 2026)**, E4B vía **Ollama en MacBook M4 Pro 24 GB**: **57 tok/s**.
- **alphasignalai.substack.com**: "*on a MacBook Pro M5 Max with 48 GB unified memory, Gemma 4 26B A4B reaches over 100 tokens per second through native Swift and the MLX framework*" — no es E4B, pero da una cota superior para Apple Silicon.
- El claim viral de Facebook "0xSojalSec" sobre "400 tokens per second" en MacBook M5 con E4B **es no verificable** (sin método ni log) y debe descartarse.
- Tamaño Q4_K_M oficial (bartowski): 5.41 GB; pesos del decoder 2.24 GB + 0.67 GB embeddings (model card litert-community).

**Para GPUs ~6 GB / RTX clase Ampere/Ada 8 GB (3050/3060/4060/2060/2070)**: **NO encontré números publicados** en Unsloth docs, model card de litert-lm, bartowski, Reddit r/LocalLLaMA ni issues de llama.cpp para E4B-Q4_K_M específicamente. Extrapolación razonable (basada en bandwidth memory ratio 5060 vs Ampere/Ada 8 GB): probablemente **35–55 tok/s decode** en una 4060/3060 8 GB, pero **debe medirse en el sistema real**.

**LiteRT-LM benchmarks oficiales**: 1024 prefill / 256 decode @ 2048 ctx con XNNPACK + 4 threads en CPU — no comparable directamente a llama.cpp + CUDA en RTX, pero valida que el modelo es operable on-device.

**Reducir tokens de decode**:
1. Apagar thinking (`<|think|>` removido del system) → ahorra cientos de tokens por query compleja.
2. Forzar respuestas cortas con `max_tokens` agresivo + instrucción en system prompt.
3. Usar `tool_choice: "required"` + GBNF para forzar emit de tool_call inmediato sin preámbulo verbal.
4. Sampling oficial recomendado: **temp = 1.0, top-p = 0.95, top-k = 64** (Google defaults, Unsloth docs); penalización de repetición desactivada (= 1.0) salvo loops.
5. **`-np 1`** (mono-usuario) reduce el SWA cache ~3× — crítico en 6 GB VRAM.
6. **`-fa 1`** (flash attention) obligatorio para contextos largos y para que SWA funcione bien.

---

## 8) Documentación oficial y diferencias vs Gemma 3 / 3n

**Fuentes primarias confirmadas**:
- Blog Google DeepMind: blog.google/innovation-and-ai/technology/developers-tools/gemma-4/ — 2-Abr-2026.
- Página DeepMind: deepmind.google/models/gemma/gemma-4/.
- Model card y overview: ai.google.dev/gemma/docs/core y ai.google.dev/gemma/docs/core/model_card_4 (última actualización 5-May-2026).
- Releases page: ai.google.dev/gemma/docs/releases — confirma "Release of Gemma 4 - MTP for E2B, E4B, 31B, and 26B A4B" y "Release of Gemma 4 in E2B, E4B, 31B and 26B A4B sizes".
- Function calling guide: ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4.
- MTP overview: ai.google.dev/gemma/docs/mtp/overview, ai.google.dev/gemma/docs/mtp/mtp.
- Blog MTP: blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/.
- Hugging Face: huggingface.co/google/gemma-4-E4B, huggingface.co/google/gemma-4-E4B-it, huggingface.co/google/gemma-4-E4B-it-assistant, huggingface.co/blog/gemma4.
- Ollama: ollama.com/library/gemma4:e4b.
- vLLM: docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html.

**Diferencias clave Gemma 3 → Gemma 4**:

| Aspecto | Gemma 3 / 3n | Gemma 4 |
|---|---|---|
| Tamaños | 1B/4B/12B/27B (3); E2B/E4B (3n) | E2B/E4B/26B A4B MoE/31B Dense |
| Licencia | Custom Gemma | **Apache 2.0** (sin restricciones MAU) |
| MoE | No | **Sí (26B A4B, 128 expertos)** |
| Contexto | 128K | 128K (small) / **256K** (medium) |
| Audio nativo | Sólo Gemma 3n (E2B/E4B) | E2B/E4B nativo, conformer USM |
| Video | No | 26B/31B (1 fps hasta 60 s) |
| Function calling | Parcial / experimental | **Nativo con tokens dedicados** |
| Thinking mode | No (en 3) | **Sí, toggleable** `<|think|>` |
| System role | No nativo | **Sí, nativo** |
| Speculative decoding | No | **MTP drafters oficiales** (todos los tamaños) |
| Atención | iSWA (5:1 ratio en 3) | iSWA híbrida + unified KV + p-RoPE en globales |
| AIME 2026 | 27B = 20.8 % | 31B = **89.2 %**, E4B = **42.5 %** |
| τ²-bench | 27B = 6.6 % | 31B = **86.4 %** |

Gemma 4 mantiene la idea PLE de Gemma 3n para los modelos "E", pero **el resto de la arquitectura es nuevo** (incluyendo el sistema de tokens de control, function calling nativo, soporte MTP oficial, MoE 26B). NO se debe asumir que parámetros y comportamientos de Gemma 3n E4B se aplican literalmente a Gemma 4 E4B.

---

## Recomendaciones para tu auditoría del perfil "vram4"

**Inmediatas (cambios de configuración recomendados en llama-server)**:
1. **Quitar `--swa-full`** del lanzamiento → libera VRAM al usar el SWA cache compacto e iSWA correctamente.
2. **Añadir `-np 1`** → reduce SWA cache ~3× (mono-usuario, voice assistant local).
3. **Añadir `-fa 1`** (flash-attention) si no está; obligatorio para SWA híbrida.
4. **`--jinja`** activado → asegura el chat template oficial y el parser tool-call `peg-gemma4`.
5. **NO usar `--draft` / `--model-draft`**: en 6 GB es contraproducente, y el drafter MTP oficial no está en mainline b9090.
6. **Tool-calling**: NO usar `--json-schema` (crash en E4B, issue #22396). Usar `--grammar-file` con GBNF manual que constraint estructura + tipos de argumentos. Limitar a ≤10 tools, descripciones distintivas, `tool_choice: "required"` en queries que esperen una llamada.
7. **Thinking mode**: **desactivado por defecto** (no incluir `<|think|>` en system prompt). Activar opcionalmente sólo para queries marcadas como complejas.
8. **Sampling**: temp=1.0, top_p=0.95, top_k=64; rep_penalty=1.0.
9. **mmproj de 990 MB**: si el voice assistant no necesita visión, **no cargarlo**. Si sí (audio = ASR vía mmproj), considerar offload parcial (`-ngl`) para dejarlo en CPU/RAM y mantener todos los layers del LLM en GPU. Cuidado con el assert error del audio (issue #21816).

**Umbrales para reconsiderar arquitectura**:
- Si la latencia de decode > 150 ms/token → migrar a fork ik_llama.cpp con MTP (necesita ≥12 GB VRAM) o aceptar CPU+GPU mixto con `-ngl` parcial.
- Si las llamadas a herramientas fallan > 10 % en validación → cambiar a 26B A4B Q4_K_M (necesita ≥16 GB VRAM) o reforzar GBNF y/o reentrenar tools con descripciones más estrictas.
- Si TTFT > 5 s en system prompts grandes → revisar issue #21468 (cache reuse roto con `--swa-full`), aplicar workaround o actualizar a build > b9090.

**Verificar contra el sistema real (no asumir)**:
- Tokens/sec de decode en el GPU real (no extrapolar de RTX 5060 8 GB; los números fiables son 72 t/s en RTX 5060 8 GB y 57 t/s en MacBook M4 Pro 24 GB, no hay datos públicos para RTX 3050/3060/4060 ni laptops Ampere/Ada).
- Tasa de aceptación de tool-calls al 4-bit en el dominio del voice assistant (no extrapolar el 15 % de error del 31B).
- Comportamiento del audio mmproj (issue #21816 puede causar crash con clips largos).
- Memoria total con context típico del workload (no 8K teórico).
- Versión exacta del fix #21434 en b9090 (verificar logs `print_info: n_embd_k_gqa`).

---

## Caveats y conflictos entre fuentes

- **Drafter E4B parameter count**: **78.8 M es la cifra autoritativa** según el HF card de AtomicChat/gemma-4-E4B-it-assistant-GGUF (verbatim: "Approximate size: 78.8M (assistant) / 8B target"). La cifra de 156 M citada en Medium/kuldeepjadeja7 no está respaldada y debe descartarse.
- **Release date**: 2-Abr-2026 (Google blog, Wikipedia, HF) vs 31-Mar-2026 (aurigait.com). Primario manda → 2-Abr.
- **Soporte mainline llama.cpp para MTP en b9090**: forks-only, confirmado por múltiples fuentes (Discussion #22735 sin merge, PR #22673 Qwen-only y en draft, AtomicChat HF advierte explícitamente "*will not load in stock llama.cpp*"). Subir a builds posteriores o cambiar a fork ik_llama.cpp si se necesita el speedup.
- **Tokens/sec específicos en RTX 3050/3060/4060 8 GB para E4B Q4_K_M**: **NO localizados públicamente**. Puntos firmes: RTX 5060 8 GB = 72 t/s (InfoWorld, LM Studio); MacBook M4 Pro 24 GB = 57 t/s (kartit.net, Ollama).
- **Throughput speculative MTP**: el +60 % en E4B aplica sólo al fork de reffdev (no PR-quality). El +30–50 % de atomic-llama-cpp-turboquant aplica a 26B/31B dense, no E4B. El 2.6–2.98× de ik_llama.cpp PR #1744 fue medido en 31B Q4_K_M/Q8_0, no en E4B.
- Marketing claim "3× faster with MTP" (blog Google, Eastern Herald) sólo aplica a modelos donde MTP esté integrado y con drafter entrenado; **no aplicable** a llama.cpp mainline b9090 con E4B.
- Aurigait y otros blogs secundarios mezclan a veces fechas y términos; preferir model card oficial.
- El claim viral de Facebook "0xSojalSec" de 400 tok/s en MacBook M5 con E4B no es verificable y debe descartarse para cualquier propósito de auditoría.