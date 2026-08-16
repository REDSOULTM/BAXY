# Carter v4 — Gemma 4 (E2B / E4B) en Ollama 0.20.4: Investigación Técnica y Decisión

**TL;DR**
- **No migres a Gemma 4 E4B como LLM principal de Carter v4.** En RTX 4060 Ti 16 GB con Ollama 0.20.4, el tag oficial `gemma4:e4b` (= `gemma4:e4b-it-q4_K_M`, 9.6 GB en disco / ~10–11 GB en VRAM con KV cache) cuesta **~4× la VRAM** de `qwen3:4b-instruct-2507-q4_K_M` (2.5 GB) sin ganancias claras en tool calling agéntico, y arrastra bugs activos de parser de tool_calls justo en la combinación que Carter usa (system prompt + tools + `think:false`).
- **No existe en Ollama un tag “Gemma 4 E4B solo-texto Q4_K_M” comparable directo a qwen3:4b** en RTX 4060 Ti. El default Q4_K_M incluye encoders de visión (~150 M) y audio (~300 M) + proyectores BF16, lo que infla el peso a 9.6 GB; los tags solo-texto (`e4b-nvfp4`, `e4b-mxfp8`) son formatos NVFP4/MXFP8 pensados para Blackwell (RTX 50xx), no para Ada (RTX 40xx) — corren, pero sin la aceleración nativa.
- **Uso secundario sí tiene sentido:** mantener `gemma4:e4b-it-q4_K_M` como **VLM/ASR on-demand** (load/unload con `keep_alive=0`) para visión y voz cuando llegue esa fase de Carter, conservando `qwen3:4b-instruct-2507-q4_K_M` como cerebro agéntico residente. La MTP (multi-token prediction, 2–3× speedup) **aún no está en Ollama para Windows/CUDA** a mayo 2026 — solo Mac/MLX.

---

## Key Findings

### 1) Identidad real del modelo
“Gemma 4” **sí existe** y es independiente de Gemma 3n. Lanzado por Google DeepMind el **2 abr 2026** bajo Apache 2.0, derivado de la misma investigación que Gemini 3. La familia tiene cuatro tamaños: **E2B**, **E4B**, **26B-A4B (MoE)** y **31B Dense**. La “E” = “effective parameters” (parameter activation selectiva, herencia de Gemma 3n). Gemma 3n sigue existiendo como producto separado en Ollama (`gemma3n:e2b/e4b`, contexto 32K, solo texto, 5.6/7.5 GB). **Gemma 4 E2B/E4B son los reemplazos directos** y añaden vision + audio nativo + 128K context + función de thinking + tool calling nativo.

### 2) Tabla completa de tags de `gemma4` en Ollama (extraída de `ollama.com/library/gemma4/tags`, 6.5 M downloads, 29 tags actualizados ~mayo 2026)

| Tag | Tamaño disco | Contexto | Modalidades | Notas para RTX 4060 Ti 16 GB |
|---|---|---|---|---|
| `gemma4:latest` (= `e4b-it-q4_K_M`) | 9.6 GB | 128K | Text, Image, Audio | Default. Incluye mmproj BF16 |
| `gemma4:e2b` (= `e2b-it-q4_K_M`) | 7.2 GB | 128K | Text, Image, Audio | Cabe holgado |
| `gemma4:e2b-it-q8_0` | 8.1 GB | 128K | Text, Image, Audio | Q8 mantiene mmproj |
| `gemma4:e2b-it-bf16` | 10 GB | 128K | Text, Image, Audio | BF16 |
| `gemma4:e2b-mlx-bf16` | 10 GB | 128K | **Text only** | MLX → solo Apple Silicon |
| `gemma4:e2b-mxfp8` | 7.9 GB | 128K | **Text only** | MXFP8 (Blackwell-optimizado) |
| `gemma4:e2b-nvfp4` | 7.1 GB | 128K | **Text only** | NVFP4 (RTX 50xx) |
| `gemma4:e4b` (= `e4b-it-q4_K_M`) | **9.6 GB** | 128K | Text, Image, Audio | **Tag de comparación** |
| `gemma4:e4b-it-q8_0` | 12 GB | 128K | Text, Image, Audio | |
| `gemma4:e4b-it-bf16` | 16 GB | 128K | Text, Image, Audio | Justo en el límite |
| `gemma4:e4b-mlx-bf16` | 16 GB | 128K | Text only | Apple Silicon only |
| `gemma4:e4b-mxfp8` | 11 GB | 128K | **Text only** | Sin mmproj — útil pero MXFP8 |
| `gemma4:e4b-nvfp4` | 9.6 GB | 128K | **Text only** | NVFP4 — no acelera en Ada |
| `gemma4:26b` (= `26b-a4b-it-q4_K_M`) | 18 GB | 256K | Text, Image | MoE: 25.2B total / 3.8B active |
| `gemma4:26b-a4b-it-q8_0` | 28 GB | 256K | Text, Image | No cabe |
| `gemma4:26b-mxfp8` | 27 GB | 256K | Text only | No cabe |
| `gemma4:26b-nvfp4` | 17 GB | 256K | Text only | Cabe ajustado, NVFP4 no acelera |
| `gemma4:26b-mlx-bf16` | 52 GB | 256K | Text only | n/a |
| `gemma4:31b` (= `31b-it-q4_K_M`) | 20 GB | 256K | Text, Image | No cabe en VRAM |
| `gemma4:31b-it-q8_0` | 34 GB | 256K | Text, Image | n/a |
| `gemma4:31b-it-bf16` | 63 GB | 256K | Text, Image | n/a |
| `gemma4:31b-cloud` | n/a | 256K | Text, Image | Solo Ollama Cloud |
| `gemma4:31b-mxfp8` | 32 GB | 256K | Text only | n/a |
| `gemma4:31b-nvfp4` | 20 GB | 256K | Text only | NVFP4 — sólo cabe en RTX 5090 |
| `gemma4:31b-mlx-bf16` | 63 GB | 256K | Text only | n/a |

**Datos arquitecturales E4B (oficiales):** 4.5 B effective / 8 B con embeddings, 42 layers, sliding window 512, 128K context, vocab 262 K, vision encoder ~150 M, audio encoder ~300 M.

### 3) Por qué los “8.95 GB / 10.5 GB en VRAM” que mediste son normales (no bug)
La doc original prometía “3.5–5 GB Q4” midiendo **solo los pesos del LM** (4.5 B × 0.5 byte ≈ 2.25 GB; con embeddings sin compartir y la lookup table 262 K × 2560 ≈ +1.3 GB). El tag de Ollama `e4b-it-q4_K_M` empaqueta también **el vision encoder + el audio encoder + el proyector multimodal BF16 unificado** (~3–4 GB extra) porque son 1411 tensores que deben quedar en BF16 (no caben en bloques K-quant). Resultado: 9.6 GB en disco. En tiempo de carga, sumado al KV cache de un 128K window con sliding 512 + flash-attention buffers, se estabiliza en **10–11 GB residentes**. Tu medición empírica (10.5 GB) coincide con todos los reportes. **No es un fallo de descarga ni cuantización corrupta.**

### 4) ¿Hay un tag E4B Q4_K_M solo-texto? — No, en sentido estricto
Los únicos tags solo-texto de E4B son `mxfp8` (11 GB), `nvfp4` (9.6 GB) y `mlx-bf16` (16 GB). En **RTX 4060 Ti (Ada Lovelace, sm_89)**:
- `nvfp4` requiere instrucciones **Blackwell FP4** (sm_120/sm_121); en Ada caerá a un kernel de emulación con peor performance que Q4_K_M.
- `mxfp8` requiere MXFP8 (también Blackwell); en Ada idem.
- Por eso, **el tag más justo para benchmark contra `qwen3:4b-instruct-2507-q4_K_M` en RTX 4060 Ti es `gemma4:e4b-it-q4_K_M`**, asumiendo que el coste extra de mmproj se contabiliza como overhead realista del modelo multimodal (es lo que un usuario va a tener).

### 5) Tool calling en Ollama 0.20.4 — estado real (esto es decisivo)
- **Ollama 0.20.4 (07 abr 2026):** changelog literal = *“gemma4: enable flash attention”* + mejoras MLX/M5. **No incluye fixes del tool parser.** Los fixes vinieron después.
- **Bugs verificados activos contra 0.20.4 y posteriores:**
  - **Issue #15241** (Ollama): `gemma4 tool call parsing failed: invalid character 'p' after object key:value pair` — afecta a Codex/OpenCode/LiteLLM.
  - **Issue #15315**: persiste en 0.20.1.
  - **Issue #15539** (crítico para Carter): cuando combinas **system prompt + `think:false` + tools** (exactamente la receta agéntica), el parser de Ollama falla y los `tool_calls` se filtran como texto crudo en `content`. Tres permutaciones probadas: sin system → ✅; con system + thinking → ✅ pero con 14 s de cadena de pensamiento perdida; con system + `think:false` → ❌ tool_calls roto.
  - **Issue #15798**: hasta 0.21.1 todavía aparecen tokens `<|tool_call|>`, `<|"|>`, `<|channel|>` filtrados como texto en algunos paths.
  - **Issue #15719**: en LiteLLM con 0.20.6/0.20.7 → loop infinito de tool calls. Workaround = downgrade a 0.20.5.
  - **Issue #20995** (OpenCode): `tool_calls` correctamente generados pero el cliente no los reconoce vía OpenAI-compat con streaming.
- **El renderer fue rehecho varias veces:** 0.20.7 “Restored the Gemma 4 nothink renderer with the e2b-style prompt”; 0.21.0/0.22.0 “Improved Gemma 4 tool calling with Google's latest fixes”; 0.22.1 “Updated the Gemma 4 renderer for thinking and tool calling improvements”; 0.23.0 (28 abr 2026) afina parallel tool calls. **Es decir, en 0.20.4 estás en una versión inestable para tool calling con Gemma 4.** Carter v4 valida 90 % en 540 casos *con qwen3* — replicar esa matriz con gemma4 en 0.20.4 implica luchar contra bugs que ya están parcialmente fixed en 0.22.1+.
- **Sampling oficial de Google para Gemma 4** (de Modelfile en Ollama): `temperature=1.0`, `top_p=0.95`, `top_k=64`. No menciona `repeat_penalty` (de hecho **el Go runner de Ollama ignora silenciosamente penalties** — issue #14493). Compárese con qwen3-instruct: `temp=0.7`, `top_p=0.8`, `top_k=20`, `min_p=0`, `presence_penalty≈1.0`. **Son configs incompatibles** — no puedes reutilizar tu sampler tal cual.
- **Thinking mode:** en E2B/E4B se activa **incluyendo el token literal `<|think|>` al inicio del system prompt**; quitarlo lo desactiva. A diferencia de los modelos grandes, las variantes E2B/E4B sí dejan limpio el output cuando se desactiva (no emiten bloque thought vacío). En multi-turn, **no debes feedback de bloques de pensamiento previos** a la siguiente turn (rule oficial de Google).
- **`/api/chat` vs `/api/generate`:** solo `/api/chat` pasa los `tool_calls` por el parser; `/api/generate` ignora la plantilla de tools. Para Carter usa `/api/chat`.

### 6) Latencia y tokens/s empíricos (RTX 4xxx, abril–mayo 2026)
- **RTX A6000 (referencia upper bound):** E4B BF16 = 13.82 tok/s, TTFT bajo, 16 GB usados; E2B = 16.93 tok/s, 61 ms TTFT (DEV.to bench, abr 2026).
- **RTX 4090 + vLLM v0.19.0 (issue #38887):** Gemma 4 E4B = **~9 tok/s** (¡!) porque vLLM se ve forzado a TRITON_ATTN por *heterogeneous head dimensions* (256 vs 512 sliding/global) y desactiva FlashAttention. Llama-3.2-3B comparable da 100+ tok/s en el mismo hardware. Esto es un cuello de botella **arquitectural**, no de cuantización.
- **NVIDIA Jetson/Spark/Mac M3 Ultra benchmarks oficiales** (Q4_K_M, BS=1, ISL=4096, OSL=128, llama.cpp b7789): publicados pero no incluyen RTX 40xx en la tabla NVIDIA.
- **No existen benchmarks públicos de gemma4:e4b vs qwen3:4b en RTX 4060 Ti específicamente** a mayo 2026. Lo más cercano es Daniel Vaughan (codex.danielvaughan.com, abr 2026) que reporta sobre Mac M5 + GB10 (no Ada): *“On the GB10, use Ollama v0.20.5 with the 31B Dense. Everything else we tried either crashed, froze, or failed to call tools.”*
- **MTP en NVIDIA consumer:** Google anunció el 5 may 2026 los drafters MTP (`google/gemma-4-E2B-it-assistant`, etc.) bajo Apache 2.0 con 2–3× speedup. Compatibilidad declarada: HF Transformers, MLX, vLLM, SGLang, **Ollama**, LiteRT-LM. Pero las release notes de Ollama (0.22/0.23) dicen literalmente: *“Gemma 4 MTP speculative decoding is now supported **on Macs**. This can give over a 2x speed increase for the Gemma 4 31B model on coding tasks.”* — **Windows/CUDA todavía no en mayo 2026**. Build Fast with AI confirma: *“Ollama support is listed as part of the ecosystem but is still being validated across versions as of May 2026. Hugging Face Transformers and vLLM are the most stable and well-documented paths for MTP integration today.”* Para Carter, esto cancela el supuesto 3× sobre Windows.

### 7) Benchmarks publicados (oficiales, modelo card de Ollama/Google)

| Métrica | Gemma 4 E4B | Gemma 4 E2B | Qwen3-4B-Instruct-2507 |
|---|---|---|---|
| **Tau2 (avg of 3) — agentic tool use** | **42.2 %** | 24.5 % | (no publicado idéntico; Qwen3-4B-Thinking reporta BFCL-v3 = 71.2 %) |
| MMLU Pro | 69.4 % | 60.0 % | competitivo (Arendil reporta Qwen3.5-4B ahead en casi todo) |
| LiveCodeBench v6 | 52.0 % | 44.0 % | — |
| GPQA Diamond | 58.6 % | 43.4 % | — |
| AIME 2026 no tools | 42.5 % | 37.5 % | — |
| MMMLU (multilingual) | 76.6 % | 67.4 % | — |
| BigBench Extra Hard | 33.1 % | 21.9 % | — |
| Audio CoVoST | 35.54 | 33.47 | — (no audio nativo) |
| Vision MMMU Pro | 52.6 % | 44.2 % | — (no visión nativa) |

**Lectura honesta:** el “86.4 % en Tau2” citado en blogs (Daniel Vaughan, Codex blog) corresponde a **Gemma 4 31B**, no a E4B. **E4B tiene 42.2 %**, que es un salto enorme contra Gemma 3 (16.2 %) pero **no ridiculiza a Qwen3-4B**, cuyo card oficial declara BFCL-v3 71.2 % (en thinking mode) y ganancias del 80 %+ en TAU benchmarks vs Qwen3 v0. En texto puro de instrucción + tool use a 4 B, **Qwen3-4B sigue por encima** según el comparativo independiente Arendil/Maniac (abr 2026): *“Qwen3.5-4B is ahead on nearly every row that matters for reasoning, science, coding, agents, and multimodal reasoning. Gemma only nudges ahead on MMMLU, and even there the gap is just 0.5 points… The Tau2 margin is especially notable.”*

### 8) Comparativa empírica para Carter v4 (RTX 4060 Ti 16 GB, Win 11, Ollama 0.20.4)

| Eje | `qwen3:4b-instruct-2507-q4_K_M` (actual) | `gemma4:e4b-it-q4_K_M` |
|---|---|---|
| Disco | 2.5 GB | 9.6 GB (~3.8× más) |
| VRAM residente (loaded) | ~3.0–3.5 GB c/8K ctx | **~10–11 GB c/8K ctx** |
| Context window | 262 K nativo | 128 K nativo |
| Tool calling parser en Ollama 0.20.4 | Estable (validado 90 %, 540 casos) | **Bugs activos #15241/#15315/#15539/#15798** — riesgo alto, fix recomendado en 0.22.1+ |
| Sampling oficial | `temp=0.7, top_p=0.8, top_k=20, presence_penalty≈1` | `temp=1.0, top_p=0.95, top_k=64` (incompatible con tu sampler actual) |
| Thinking control | No (variante Instruct, sin `<think>`) | Token literal `<|think|>` en system prompt; cuidado con la regla *“no thinking en historial multi-turn”* |
| Tool calling score (mejor proxy disponible) | BFCL-v3 71.2 % (thinking sibling); tool use sólido en producción | Tau2 42.2 % oficial |
| Latencia decode esperada (4060 Ti, Q4_K_M) | ~50–80 tok/s (típico 4 B dense en Ada) | **~10–25 tok/s** estimado por la regresión vLLM/llama.cpp por heterogeneous head dims |
| Multimodal | No (texto puro) | ✅ image + audio nativo |
| MTP speedup en Win/CUDA | n/a | **No disponible en Ollama Win/CUDA mayo 2026** — solo Mac |
| Latencia primer token (TTFT) en system prompt 5–15K (Carter usa este rango) | Bajo, FA estable en qwen3 | Riesgo: issue #15350 (FA hang con Dense >3–4K tokens prefill); E4B no afectado igual pero attention híbrida (50 SWA + 10 global, head dims 256/512) genera kernels lentos |
| Crashes en Windows | Ninguno reportado | Issue #15333 (audio crash GGML_ASSERT en Windows), #11317 (BSOD pinned-memory ggml_host_malloc — afecta múltiples modelos) |

### 9) Bugs / issues conocidos relevantes (mayo 2026, ollama/ollama)

| Issue | Versión | Síntoma | Workaround |
|---|---|---|---|
| **#15241** | 0.20.0–0.20.1 | `gemma4 tool call parsing failed: invalid character 'p'` | Upgrade a 0.20.6+ (no 0.20.4) |
| **#15315** | 0.20.1 | Tool parsing sigue roto | Idem |
| **#15539** | 0.20.6 | system prompt + `think:false` + tools → tool_calls leak a `content` | Mantener thinking ON o quitar system prompt (inviable para Carter) |
| **#15798** | 0.21.1 | Tokens `<|tool_call|>`, `<|"|>`, `<|channel|>` filtrados como texto vía OpenAI-compat streaming | Cerrado “will redo if needed”; sin fix definitivo |
| **#15719** | 0.20.6/0.20.7 | Loop infinito tool calls vía LiteLLM | Downgrade 0.20.5 |
| **#15333** | varios | Crash GGML_ASSERT en audio inference E4B (Windows) | Reload entre 2–4 requests |
| **#15350** | 0.20.x | FA hang en prefill >3–4K tokens (31B Dense, no E4B en NVIDIA) | `OLLAMA_FLASH_ATTENTION=0` |
| **#15237** | 0.20.0 | E2B/E4B carga en CPU pese a reportar GPU | Resuelto en 0.20.4 (precisamente este release “enable flash attention”) |
| **#11317** | varios | BSOD `ggml_host_malloc` en Windows (pinned mem) | Reducir parallel/contexto |
| **#21325 (llama.cpp)** | — | Audio Gemma 4 ausente en llama.cpp; mmproj BF16 “any-to-any” con audio vía `llama-mtmd-cli` | Solo PR en abierto |

### 10) Multimodal — ¿unificar en Gemma 4 o mantener stack separado?
- **Realidad audio:** E4B sí tiene encoder audio nativo (~300 M params, FLEURS WER 0.08, CoVoST 35.54), **pero su soporte en Ollama Windows es inestable** (crash intermitente #15333). En Mac/MLX está mejor cubierto. Es una **STT contextual/comprensión**, no un Whisper sustituible (no produce timestamps, no es streaming, calidad decente pero no SOTA en transcripción larga).
- **Realidad visión:** OmniDocBench 0.181 (E4B), MMMU Pro 52.6 %, MATH-Vision 59.5 %. Suficiente para OCR de UI, descripción de pantalla, lectura de documentos cortos. Para visión intensiva (UI parsing fino, cropping, multi-screen 4K que Carter ya captura como “virtual screen completo”) un VLM dedicado como `qwen2.5-vl-7b` (Q4 ≈ 5 GB) o `qwen3-vl` rinde mejor.
- **Coste residente:** Gemma 4 E4B residente = ~10–11 GB → solo te dejan **~5 GB libres** para verifier numpy + Win32 + KV cache de cadenas largas + buffers de captura virtual. Apretado.
- **Coste swap on-demand:** `ollama` con `keep_alive=0` descarga al terminar la request. Reload de E4B (9.6 GB en disco, ~10 GB VRAM) tarda ~3–6 s en SSD NVMe + PCIe 4.0. Aceptable para visión/voz que ocurren en eventos discretos, **inviable para el bucle ReAct de 25 s budget/turn donde dispararías 1–3 reloads por turn**.

---

## Details

### Recomendación de Modelfile para benchmark justo (si decides correrlo de todos modos)
```
FROM gemma4:e4b-it-q4_K_M
PARAMETER temperature 1.0
PARAMETER top_p 0.95
PARAMETER top_k 64
PARAMETER num_ctx 8192          # match a tu config qwen3
PARAMETER num_predict 1024
# DESACTIVAR thinking en E4B: NO incluir <|think|> en system prompt
SYSTEM """Eres Carter, asistente local. Responde con función-llamada cuando proceda."""
```
Y en lado cliente: usar **estrictamente `/api/chat`** (no `/v1/chat/completions` OpenAI-compat — ese tiene los bugs #15798/#20995 más severos). **Upgrade obligatorio a 0.22.1+** antes del bench, o los resultados serán contaminados por bugs de parser ya solucionados.

### Sobre el “3× con MTP”
- Es real en Mac (MLX) y en vLLM/Transformers para Linux con Hopper/Blackwell. Para Carter (Windows + RTX 4060 Ti + Ollama) **no aplica hoy**. Cuando Ollama suba MTP a CUDA Win, además, el draft model (`gemma-4-E4B-it-assistant`) añade ~500 MB extra al footprint y comparte KV cache con el target, así que la VRAM combinada puede subir a ~11–12 GB. Sigue lejos de los 2.5 GB de qwen3.
- Para 26B-A4B la propia doc de Google reconoce que MTP rinde menos a batch=1 (caso típico de Carter) por el overhead de cargar expertos extra al verificar drafts.

### Por qué Gemma 4 E4B sí gana en algo
- **Audio + visión nativos** (cuando funcionen estables en Ollama Win/CUDA, post-0.23.x).
- **Multilingüe**: 140+ idiomas nativos (MMMLU 76.6 %), útil si Carter alguna vez procesa input multilingüe.
- **Long context efectivo**: MRCR v2 8-needle 128K = 25.4 % vs Gemma 3 27B 13.5 %. Si pasas a contextos >32K reales, hay margen.
- **Native function-calling format de Google** + system role nativo + Apache 2.0 (= compatible con cualquier uso comercial; igual que qwen3).

### Por qué Gemma 4 E4B pierde para Carter v4 hoy
1. **VRAM**: 4× la de qwen3 sin headroom para verifier numpy + multi-monitor capture + KV cache largo. Rompe los perfiles 6/8/10 GB de Carter (hardware-agnostic se vuelve “solo 16 GB+”).
2. **Tool calling estabilidad en Ollama 0.20.4**: bugs documentados afectan exactamente la combinación de Carter (system prompt + tools + think:false). Con qwen3 ya tienes 540/600 casos validados; partir de cero implica un nuevo gauntlet de validación + arriesgar regresiones.
3. **Latencia decode**: la attention híbrida con head_dim heterogéneo (256 sliding + 512 global) **rompe FlashAttention en kernels CUDA actuales**. vLLM cae a TRITON_ATTN y rinde 9 tok/s en RTX 4090 (vs 100+ Llama 3.2 3B). En Ollama/llama.cpp con FA enabled (0.20.4 lo activó), el patrón es similar para E4B en Ada — no hay benchmarks específicos pero la patología arquitectural es la misma.
4. **Audio crash en Windows** (#15333) = no puedes confiar el pipeline de voz al mismo modelo.
5. **MTP no disponible** en tu plataforma → el supuesto 3× speedup que cerraría el gap de latencia no es real para ti hoy.

---

## Recommendations

### Decisión final concreta (puntos A–D del briefing)

**A) Tag exacto para comparación justa Gemma 4 vs qwen3:4b en RTX 4060 Ti 16 GB:**
> `gemma4:e4b-it-q4_K_M` (alias `gemma4:e4b`, blob `c6eb396dbd59`, 9.6 GB disco, 128K ctx, Q4_K_M con vision+audio mmproj BF16). Es el único Q4_K_M E4B publicado por Ollama; los tags solo-texto disponibles (`mxfp8`, `nvfp4`) requieren Blackwell para ejecutarse aceleradamente. **Si vas al bench, además: upgrade a Ollama ≥ 0.22.1, sampling `temp=1.0/top_p=0.95/top_k=64`, /api/chat, system prompt sin `<|think|>`.**

**B) ¿Vale la pena correr el bench?**
> **No para decidir el LLM principal.** Los datos empíricos + bugs activos en 0.20.4 + Tau2 oficial (42.2 % E4B vs ~70 %+ proxy BFCL de qwen3) + 4× VRAM ya dan veredicto. **Sí vale la pena un mini-bench de 30–50 casos** SOLO para validar gemma4:e4b como **VLM/ASR on-demand secundario**, midiendo: (1) latencia de carga/descarga, (2) calidad OCR de capturas Win32, (3) estabilidad del pipeline audio en sesiones cortas (<3 requests entre reloads para evitar #15333).

**C) Si Gemma 4 ganara (no es el caso, pero por completitud):** los cambios mínimos serían: (1) bumpear Ollama a ≥0.22.1; (2) sampler nuevo `temp=1.0/top_p=0.95/top_k=64`, eliminar `repeat_penalty`/`presence_penalty` (Gemma 4 no los recomienda y Ollama Go runner los ignora); (3) chat template: confiar en el de Ollama, no inyectar `<|think|>` en system prompt (mantener thinking OFF para latencia agéntica); (4) en ReAct multi-turn, **podar bloques de pensamiento previos del historial** antes de la siguiente turn (regla oficial); (5) ajustar perfil VRAM: eliminar perfiles 6/8 GB o degradar a `gemma4:e2b` (7.2 GB) en esos perfiles; (6) verifier estructural: el padding/dims del KV cache cambia, recalibrar el frame-diff numpy para nuevos timings; (7) function calling: sigue siendo OpenAI-style en `/api/chat`, no necesitas reescribir el adapter, pero sí añadir un *strip-leak* para tokens `<|tool_call|>`/`<|channel|>` por si Ollama no los filtra (defensive parsing).

**D) ¿Uso secundario con sentido?**
> **Sí, condicional y diferido.** Recomendación staged:

1. **Fase actual (mayo 2026): NO toques el modelo principal.** Mantén `qwen3:4b-instruct-2507-q4_K_M` como cerebro residente.
2. **Cuando Carter v4 entre en fase visión:** evalúa `qwen2.5-vl-7b-instruct` (~5 GB Q4) o `qwen3-vl` antes que Gemma 4 — son VLMs dedicados con Ollama estable hoy. Solo considera `gemma4:e4b-it-q4_K_M` si ya tienes presupuesto para 10 GB residentes Y necesitas el bonus de audio en el mismo modelo.
3. **Cuando Carter v4 entre en fase voz:** **NO uses Gemma 4 E4B audio en Windows** mientras #15333 esté abierto. Stack separado: faster-whisper-large-v3-turbo (CTranslate2 INT8, ~1.5 GB VRAM, streaming sub-300 ms TTFT, validado en Win) para STT + Piper o Coqui XTTS-v2 para TTS. Es el camino estable y mantiene VRAM disponible para el LLM.
4. **Reevaluación trimestral.** Triggers para reconsiderar Gemma 4 como principal:
   - Ollama publica **MTP CUDA en Windows con benchmark verificado ≥1.8× en RTX 40xx** *Y*
   - Ollama cierra los issues #15539 + #15798 + #15333 en una versión estable *Y*
   - Aparece tag `gemma4:e4b-it-q4_K_M-text-only` (sin mmproj) **<5 GB** en disco *Y*
   - Bench independiente reproduce ≥30 % ventaja absoluta de E4B sobre qwen3-4B en BFCL-v3 o TAU2 con misma config.
   Sin ≥3 de esos 4 cumplidos, sigue con qwen3.

### Cómo orquestar el secundario on-demand sin romper el budget de 25 s/turn
- Carga gemma4 con `keep_alive=120s` solo cuando el agente decida invocar visión/audio (tool en el registro de 55 que dispare un **modo VLM**). Mantén qwen3 con `keep_alive=-1` (siempre warm).
- En RTX 4060 Ti 16 GB **NO caben los dos a la vez** (3 + 10 = 13 GB + KV caches → swap a system RAM y latencia se dispara). Configura `OLLAMA_MAX_LOADED_MODELS=1` y acepta el reload de 3–6 s como coste declarado en el frame visión.
- Verifier estructural numpy + Win32: documenta tiempos esperados con/sin reload para que el budget 25 s no estalle en la cadena que dispare la primera invocación VLM.

---

## Caveats

- **No existen, a fecha de mayo 2026, benchmarks públicos head-to-head de `gemma4:e4b` vs `qwen3:4b-instruct-2507` en RTX 4060 Ti específicamente.** Las cifras de latencia de gemma4 E4B en Ada son una **inferencia** desde (a) el bug vLLM #38887 que cuantifica 9 tok/s en RTX 4090 por TRITON_ATTN fallback y (b) la patología arquitectural común a llama.cpp con head_dim heterogéneo. Si haces tú la medición empírica y obtienes ≥40 tok/s, la conclusión D-fase-visión podría adelantarse, pero el resto del análisis (VRAM, tool-calling bugs, MTP no-Win) no cambia.
- **El número “6.67 GB” que reportaste para gemma4:e2b** no coincide con el actual de Ollama (7.2 GB para `e2b-it-q4_K_M`, 7.9 GB para `e2b-mxfp8`, 7.1 GB para `e2b-nvfp4`). Probablemente bajaste un build temprano (mid-abril) antes de que Google parchease el chat template (Unsloth: *“Apr 11 update: Gemma 4 is now updated with Google's updated chat template + llama.cpp fixes”*). Re-pulla con `ollama pull gemma4:e2b` para sincronizar, si lo mantienes.
- **El “86.4 % Tau2 de Gemma 4”** que circula en blogs es del **31B**, no del E4B (42.2 %). Cita propagada con frecuencia incorrecta — manténlo en mente al leer evangelizadores.
- **Las benchmarks oficiales de Google son del modelo full-precision (BF16/FP32)**, no del Q4_K_M. La degradación Q4 en E4B no está oficialmente caracterizada; Unsloth recomienda Q8 como starting point para modelos pequeños y Q4 dinámico para grandes — implica que Q4_K_M en E4B podría perder algo de tool-call accuracy frente al BF16 reportado.
- **La frase “Gemma 4 incluye thinking nativo”**: cierto pero las E2B/E4B en Ollama vienen con `temperature: 1` y sin token `<|think|>` en el params blob — o sea, **thinking OFF por default**, lo cual es bueno para Carter (latencia agéntica) pero implica que comparar con un Tau2 donde Google sí activó thinking puede ser misleading. Verifica el modo thinking en el bench si lo corres.
- **MTP CUDA en Windows está a “meses” de horizonte realista**, no semanas. La frase en blogs *“picks up the drafters with minimal configuration”* es cierta para Transformers/vLLM/SGLang pero **falsa para Ollama-Windows-CUDA en mayo 2026**. No planifiques sobre ese supuesto.
- **Ollama 0.20.4 específicamente** es una versión problemática para Gemma 4 tool calling. Si por cualquier razón terminas usando Gemma 4 (incluso solo on-demand para visión/audio), **upgradea a ≥0.22.1 antes de ese día**. Para qwen3 el 0.20.4 es perfectamente estable.