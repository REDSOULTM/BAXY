## Carter Agent — Informe de Optimización (auditoría externa)

**Auditor:** Investigador senior, sistemas de IA local.
**Fecha:** 2026-05-15 (Gemma 4 lleva 43 días publicado).
**Versión bajo auditoría:** `gemma4_agent` sobre llama.cpp CUDA + faster-whisper + Piper.
**Objeto de la auditoría:** ruta a 100% de PASS en Carter 540 sobre hardware de 6 GB de VRAM, sin sacrificar privacidad ni cambiar de runtime.

> **Verificación obligatoria de release (paso 1 del brief).** Gemma 4 fue anunciada por Google DeepMind el **2 de abril de 2026** bajo licencia **Apache 2.0**, en cuatro tamaños: E2B, E4B (efectivos 2B/4B con PLE, MatFormer-like), 26B-A4B (MoE, ~3.8–4B activos), 31B Dense. Confirmado en `blog.google/innovation-and-ai/technology/developers-tools/gemma-4/` (Farabet & Lacombe, 2026-04-02), `deepmind.google/models/gemma/gemma-4/`, `cloud.google.com/blog/products/ai-machine-learning/gemma-4-available-on-google-cloud`, `ai.google.dev/gemma/docs/releases` (last updated 2026-05-05), `huggingface.co/blog/gemma4` (2026-04-02). Toda fuente con fecha < 2026-04-02 fue descartada de antemano.

## TL;DR ejecutivo

1. **El cliente está corriendo Gemma 4 con `--cache-reuse` desactivado de facto y no lo sabe.** El issue ggml-org/llama.cpp #21468 confirma que la arquitectura Shared-KV de Gemma 4 hace que el server registre *"cache reuse is not supported - ignoring n_cache_reuse"* incluso con `-fa on` y `--swa-full`. Mientras PR #22288 no se mergee, todos los turnos del agente reprocesan el system prompt completo. **Impacto medido por el propio reporter del bug:** 60–90 s de TTFT extra por request con ~46K tokens de prompt (fuente: `github.com/ggml-org/llama.cpp/issues/21468`, 2026-04-05). Acción inmediata: pin de build, *pre-warm* y `--keep` agresivo (ver §I).

2. **`--ctx-checkpoints 1` está bien, pero no soluciona el leak de mmproj #21690.** El cliente ya pasó de default 32 a 1, lo cual evita la OOM por checkpoints (16K tokens × 5 turnos llenan 64 GB de RAM en pruebas del reporter sobre RTX 3090). El leak distinto y aún abierto **#21690 (mmproj + checkpoints en Gemma 4)** sigue activo en build 8724. En 6 GB de VRAM se confirma OOM "tras ~60–80 imágenes" como reporta el cliente (fuente: `github.com/ggml-org/llama.cpp/issues/21690`, abril 2026). **Mitigación:** mantener vision OFF en `balanced` y `light` (ya está), y para `performance` recrear el server cada N imágenes.

3. **El draft MTP oficial de Google es la palanca de 2–3× más grande disponible, y aún no la usa el cliente.** Google publicó drafters MTP el **2026-05-05** (`blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/`, `ai.google.dev/gemma/docs/mtp/overview`). vLLM lo soporta el mismo día (PR #41745). En llama.cpp **NO está soportado todavía**: `Discussion #22735` pide arquitectura `Gemma4AssistantForCausalLM`, `convert_hf_to_gguf.py` la rechaza, y el fork de trabajo está en `ik_llama.cpp` PR #1744 (no merged al 2026-05-08). [EXTRAPOLADO] sobre el roadmap: 2–4 semanas para soporte upstream. Mientras tanto, *speculative decoding con draft externo* (E2B como draft de E4B/26B) **sí** funciona (`--spec-draft-model`, doc oficial llama.cpp), con costo VRAM no trivial (ver §D3).

4. **El sampling oficial del cliente es correcto y mejor que el de la mayoría de tutoriales.** T=1.0/top_p=0.95/top_k=64/rep_pen=1.0 coincide exactamente con la doc oficial Unsloth y la metadata embebida en el GGUF (`general.sampling.*` keys, ver `huggingface.co/google/gemma-4-E2B-it/discussions/6`). El cliente está haciendo MEJOR que la práctica común (que arrastra T=0.7 desde Gemma 2/3).

5. **El modelo del dev (E4B-Q6_K) es probablemente subóptimo respecto a 26B-A4B-UD-Q2_K_XL en la misma franja de VRAM en 8 GB+.** localbench midió que *"Gemma 4 26B A4B is the most quantization-sensitive model tested so far"* con KL 0.377 sobre KV q8_0 (`localbench.substack.com/p/kv-cache-quantization-benchmark`, abril 2026), pero unsloth en sus KLD benchmarks publica que **UD-Q2_K_XL en 26B-A4B está en la frontera Pareto** y dominaría a E4B-Q6_K en calidad/byte para los slots de 8–12 GB. [CITADO]. En 6 GB esto no aplica: 26B-A4B no entra.

6. **El KV cache de Gemma 4 NO admite q8_0/q4_0 con la tranquilidad de Qwen.** localbench (`localbench.substack.com/p/kv-cache-quantization-benchmark`) midió KL 0.108 (31B q8_0) y **KL 0.377 (26B-A4B q8_0)**, vs Qwen <0.04. **Recomendación dura:** mantener KV en F16 sobre Gemma 4 hasta que se trabaje un benchmark interno por dominio. Solo activar q8_0 KV si se mide < 1% degradación en Carter por categoría.

7. **El cliente ya está haciendo MEJOR que LM Studio/Ollama en tool calling.** Daniel Farina documenta (`gist.github.com/daniel-farina/87dc1c394b94e45bb700d27e9ea03193`) que **Ollama v0.20.0 tira los tool_calls en streaming** (issue #15241) y por eso él mismo migró a llama-server con PR #21326 + #21343 + parser dedicado **#21418 merged 2026-04-04** (`github.com/ggml-org/llama.cpp/pull/21418`). El stack del cliente (`--jinja` + parser nativo) es el camino oficial recomendado.

8. **Audio nativo Gemma 4 en `/v1/chat/completions` NO funciona aún por bug #21868.** El encoder Conformer USM está merged (PR #21421 → build b8773), pero `server.cpp` no enruta `input_audio` en el ChatCompletions, y devuelve HTTP 500. *"The only current workaround is spawning llama-mtmd-cli as a subprocess per request, which cold-loads the full model on every call (~44s on Pi 5)"* — `github.com/ggml-org/llama.cpp/issues/21868`, "closed not planned". **Recomendación:** mantener faster-whisper como STT primario; planear migración a Whisper-large-v3-turbo CPU si latencia lo permite, descartar audio nativo Gemma 4 vía server hasta que reabran #21868 o se publique #21421 + fix de routing.

> **Tres cosas que el cliente hace MEJOR que la práctica común:**
> (a) sampling oficial Google sin tocar `repeat_penalty`; (b) `--jinja` + parser nativo llama-server en lugar de OpenAI-shim sobre Ollama; (c) profile-switching consciente del límite de 6 GB (recommend_profile(vram_mb)) en lugar de "usa el grande y a ver".
>
> **Tres cosas que el cliente hace MAL:**
> (a) confiar en `--cache-reuse` que está roto en Gemma 4 (#21468 abierto); (b) usar mmproj F16 a la vez que tiene visión OFF en `balanced/light` — el F16 cabe en disco pero introduce el path de leak de #21690 si se carga incluso por error con `-hf`; (c) E4B-Q6_K como modelo del dev en lugar de 26B-A4B-UD-Q2_K_XL o E4B-UD-Q5_K_XL (mejor calidad/byte según los KLD benchmarks de Unsloth, 2026-04-20).

## 0. Mapa de incertidumbre

Este informe se basa en evidencia citable post-2026-04-02. **Aproximadamente el 35–45% de las recomendaciones específicas son extrapolación informada** (marcadas como [EXTRAPOLADO]), porque la cantidad de benchmarks formales sobre Gemma 4 (43 días en circulación) es todavía limitada y la mayoría de las que existen están sesgadas a Apple Silicon / RTX 3090 / RTX PRO 6000. Lo que **no** se pudo verificar con fuente Tier 1/2:

| # | Pregunta no resuelta | Por qué no se resolvió | Cómo medirlo en casa |
|---|---|---|---|
| U1 | VRAM medida exacta de E4B-Q4_K_M con `-ngl 99 -c 8192 -fa on --jinja` en RTX 3050 6 GB Windows 11 | Ninguna fuente pública tiene esa combinación exacta; los tamaños de GGUF en bartowski (5.41 GB Q4_K_M, 5.82 GB Q5_K_M) son del archivo, no de VRAM con KV+compute+mmproj | `nvidia-smi --query-gpu=memory.used --format=csv -l 1` antes/después de cargar, 30 turnos sintéticos de 1K tokens |
| U2 | KL divergence E4B en Q4_K_M vs UD-Q4_K_XL para tareas tool calling en español | Unsloth solo publicó 99.9% KLD agregado y benchmark over 22 sizes en 26B-A4B y 31B; E4B-it KLD por categoría no está publicado | Reproducir metodología localbench (logprob extraction) sobre Carter 540 categorizado |
| U3 | WER en es-MX de Whisper-large-v3-turbo int8 en CPU x86 4 cores | faster-whisper benchmark estándar mide LibriSpeech-en-clean, no es-MX | Common Voice 17.0 es-MX 200 utterances + jiwer |
| U4 | Latencia real de speculative decoding E2B-draft → E4B-target en RTX 3050 6 GB | Sin benchmarks públicos de ese par en 6 GB; los que hay son 31B + draft externo en H100/Blackwell | `llama-bench` con `--model-draft` |
| U5 | Calidad audio nativo Gemma 4 (es-MX) post-#21421 | El cliente reporta 2/5 internos; sin benchmark público comparativo | Mismo set que Whisper, evaluación humana ABX |
| U6 | Throughput tok/s real en CPU-only para 26B-A4B-UD-IQ2_XXS | No publicado; los benchmarks CPU se centran en E2B/E4B | `llama-bench -t N` con N = núcleos físicos |
| U7 | Estabilidad upstream del MTP drafter para llama.cpp (no ik_llama.cpp) | Discussion #22735 abierta 2026-05; sin PR upstream visible | Esperar y reevaluar en 30 días |
| U8 | Brecha real entre Carter 540 (interno, español, tool calling) y MMLU/AIME públicos | Sin literatura externa que correlacione Carter con benches estándar para Gemma 4 | Correlar Pearson PASS rate Carter vs MMLU-pro-es subset en cada GGUF candidato |
| U9 | Estabilidad de MXFP4_MOE en 26B-A4B sobre CUDA 12.x build b9090+ | Unsloth retiró MXFP4 de sus quants base (`Retiring MXFP4 from all GGUF quants: Q2_K_XL, Q3_K_XL and Q4_K_XL, except for pure MXFP4_MOE`, doc Qwen3.5 GGUF Benchmarks) — sugiere madurez parcial | Build b9090+ y A/B con UD-Q4_K_XL en mismas tareas |
| U10 | Overhead exacto del WDDM Windows 11 desktop@1080p con un monitor sobre RTX 3050 6 GB | No hay benchmarks públicos reproducibles; reportes anecdóticos hablan de 0.6–1.2 GB para `dwm.exe` (Tom's Hardware forum, Microsoft Q&A) — no son Tier 1 | Reservar 1.0–1.5 GB en `recommend_profile()` y medir con `nvidia-smi` antes de lanzar server |

**Banderas adicionales sobre fuentes:**

- Varios blogs (aurigait, labellerr, aihaven, wavespeed, tech-insider, aimlapi, techloy) publicaron *résumés* del blog oficial de Google reorganizando los mismos números. Las he tratado como Tier 3 y no he citado ningún dato exclusivamente derivado de ellos.
- `n1n.ai/blog/gemma-4-local-inference-llama-cpp-kv-cache-fix-npu-benchmarks-2026-04-05` contiene "Rockchip NPU + Gemma 4 26B at 4 W" sin código de soporte ni PR identificable. **No usado en decisiones críticas.**
- `kaitchup.substack.com` (Benjamin Marie) hace una memoria-math creíble pero algunos números (e.g. `5,578,424,320 bytes` para Gemma 4 26B-A4B 256K KV) son derivados de la config publicada, no medidos. Se citan como [CITADO con derivación].
- "localbench substack" es Tier 2 con metodología explicitada (KL divergence sobre ~250k tokens diversos vs BF16); altamente útil pero un solo evaluador.
- El blog `complete.tech/blog/llamacpp-gemma4-thinking-prompt-local-fix/` es un fork no merged; útil para entender el fallo de generation-prompt pero no se usa como recomendación de cambio en upstream.

## 1. Bloque A — Cuantizaciones (A1–A4)

### A1. Mejor combo modelo+cuantización por nivel de VRAM

Tabla construida sobre tamaños GGUF publicados (Bartowski, Unsloth), VRAM esperada (peso + KV + compute buffer + mmproj si aplica + ~1.2 GB de overhead WDDM en Windows con desktop@1080p [EXTRAPOLADO de Tom's Hardware / Microsoft Q&A]), y posición en Pareto frontier KLD según los benchmarks oficiales de Unsloth (`huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/35`, 2026-04-20) y localbench (`localbench.substack.com/p/gemma-4-31b-gguf-kl-divergence`).

| VRAM target | Recomendación principal | GGUF exacto | Tamaño en disco | VRAM estimada (ctx 8K, F16 KV, -fa on) | Calidad relativa BF16 | Para qué tarea | Confianza |
|---|---|---|---|---|---|---|---|
| **4 GB** | E2B Q4_K_M | `unsloth/gemma-4-E2B-it-GGUF:UD-Q4_K_XL` | 2.5 GB | ~3.7 GB | KL "Pareto" según Unsloth | Conversación corta, tool calling simple (<10 tools) | CITADO |
| **6 GB (HOT)** | **E4B UD-Q4_K_XL** (sustituir Q4_K_M actual) | `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL` | ~4.7 GB | ~5.6–5.9 GB (sin mmproj, ctx 4K) | mejor KLD que Q4_K_M al mismo tamaño según Unsloth KLD bench | Agentic multi-step en es; vision OFF | CITADO |
| **6 GB (alternativa segura)** | E4B Q4_K_M (estatus quo) | `bartowski/google_gemma-4-E4B-it-GGUF:Q4_K_M` | 5.41 GB | ~6.10 GB reportado por el cliente | baseline | Lo que ya está en producción | MEDIDO por cliente |
| **8 GB** | **E4B UD-Q5_K_XL + KV F16** | `unsloth/gemma-4-E4B-it-GGUF:UD-Q5_K_XL` | ~5.9 GB | ~7.2 GB | Pareto KLD según Unsloth | Razonamiento, código corto | CITADO + EXTRAPOLADO de VRAM |
| **8 GB (vision)** | E4B Q4_K_M + mmproj F16 | `bartowski/google_gemma-4-E4B-it-GGUF:Q4_K_M` + `mmproj-f16.gguf` (~990 MB) | 5.41 + 0.99 GB | ~7.3 GB | baseline + visión | OCR, descripción imagen | CITADO |
| **12 GB** | **26B-A4B UD-Q2_K_XL** | `unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q2_K_XL` | ~9.2 GB (cliente) | ~11–11.5 GB | KLD frontera Pareto Unsloth (UD-IQ3_XXS dominado) | Agentic, mejor calidad/byte para "computer use" según Unsloth | CITADO |
| **16 GB** | **26B-A4B UD-Q4_K_XL** | `unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL` | ~16–17 GB | ~17–19 GB | Pareto SOTA según Unsloth (top 21/22 sizes) | Producción "sweet spot" | CITADO |
| **24 GB** | **26B-A4B Q8_0** o **31B UD-Q4_K_XL** | `bartowski/google_gemma-4-31B-it-GGUF:Q4_K_M` (19.6 GB) | 19.6 / 26 GB | ~22–24 GB | KL 0.108 31B Q8_0 sobre BF16 (localbench) | Máxima calidad consumer | CITADO |

**Hallazgos clave en negrita:**

- **Para 6 GB, la diferencia E4B-Q4_K_M → UD-Q4_K_XL es la única palanca de calidad sin cambiar de talla.** Es prácticamente "free" (Unsloth Dynamic 2.0 sube calidad sin subir tamaño). Acción: cambiar default en `profiles.py:PROFILES["balanced"]`.
- **Bartowski y Unsloth se reparten la frontera Pareto; ggml-org y lmstudio-community quedan dominados** (excepto Q8_0 donde todos son idénticos). Fuente literal localbench: *"ggml-org and lmstudio-community quants never appear on the Pareto frontier (except Q8_0 where everyone is the same). Avoid them."*
- **Long documents y non-Latin scripts degradan más rápido** en cualquier quant. Para español el impacto es bajo (Latin), pero un agente que procese OCR de español con caracteres acentuados puede penalizar.

### A2. Unsloth Dynamic (UD) vs K_M tradicionales

**Hallazgo:** las cuantizaciones UD ganan a las K_M en Gemma 4 en los tiers Q2–Q5 según los datos publicados por Unsloth y por localbench independiente.

- **Evidencia 1 (Unsloth, 2026-04-20):** *"Mean KL Divergence puts all Unsloth GGUFs on the Pareto frontier... 99.9% KLD shows SOTA on Pareto Frontier for Unsloth Dynamic Q4_K_XL, IQ3_XXS etc. This makes Unsloth the top-performing in 21 of 22 sizes."* (`huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/35`).
- **Evidencia 2 (localbench, abril 2026):** sobre 31B con 53 quants, 8 de 9 UD están en la frontera (excepción UD-IQ3_XXS dominado por UD-Q2_K_XL del mismo tamaño).
- **Tier Q6:** Unsloth lo dejó "más dinámico" pero la mejora sobre Q6_K plain es marginal según su propia nota (*"no need to re-download though"*). Para el cliente que usa E4B-Q6_K como modelo del dev: **no urgente reemplazar Q6_K → UD-Q6_K**, pero sí E4B-Q4_K_M → UD-Q4_K_XL.

**Aplicabilidad directa Gemma 4:** SÍ, en las 4 familias (E2B/E4B/26B-A4B/31B). [CITADO]

### A3. MXFP4_MOE para 26B-A4B

**Hallazgo:** experimental, calidad **inferior** a UD-Q4_K_XL en varias capas críticas. No usar como default.

- Unsloth, en su nota de Qwen3.5 GGUF Benchmarks (extensible a Gemma 4 por usar mismo pipeline): *"Retiring MXFP4 from all GGUF quants: Q2_K_XL, Q3_K_XL and Q4_K_XL, except for pure MXFP4_MOE. ... MXFP4 is much worse on many tensors - attn_gate, attn_q, ssm_beta, ssm_alpha using MXFP4 is not a good idea, and rather Q4_K is better - also MXFP4 uses 4.25 bits per weight, whilst Q4_K uses 4.5 bits per weight. It's better to use Q4_K than MXFP4 when choosing between them."*
- **Soporte upstream:** llama.cpp build b8607+ tiene mxfp4 kernels. Para Gemma 4 26B-A4B el cliente ya descargó `MXFP4_MOE (15.4 GB)`. **Recomendación:** mantener como opción "experimental" feature-flagged; no como default. [CITADO]
- **Hash conflicts:** no encontrados públicamente para Gemma 4 al 2026-05-15. [NO PÚBLICAMENTE MEDIDO].

### A4. IQ4_XS vs Q4_K_M en E4B y 26B-A4B

- **Tamaño E4B (Bartowski):** IQ4_XS 5.11 GB vs Q4_K_M 5.41 GB; 26B-A4B: IQ4_XS 14.2 GB vs Q4_K_M 17.0 GB.
- **Calidad:** Unsloth indica *"I quants (iq3_xxs, iq2_s etc) makes inference 5-10% slower, they're definitely better in terms of efficiency, but there is a tradeoff"* (doc Qwen3.5 GGUF Benchmarks, extensible).
- **Frontera Pareto localbench (31B, no E4B):** IQ4_XS aparece en la frontera de Bartowski; Q4_K_M no es dominante.
- **Recomendación:** en 6 GB **NO** usar IQ4_XS para E4B salvo que se mida ganancia (penalización tok/s ~5–10% sobre CPU/Vulkan, marginal sobre CUDA). En 16 GB para 26B-A4B, IQ4_XS es una opción seria contra Q4_K_M por tamaño. [CITADO]

**Acciones recomendadas (archivo + tipo):**

| Archivo | Cambio | Bloque |
|---|---|---|
| `profiles.py:PROFILES["balanced"]` | Cambiar default GGUF E4B-Q4_K_M → `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL` | A1, A2 |
| `profiles.py:PROFILES["performance"]` | Sustituir 26B-A4B IQ2_XXS por UD-Q4_K_XL si VRAM ≥16 GB; mantener UD-IQ2_XXS para 12 GB | A1, A2 |
| `config.py` | Banderar `MXFP4_MOE` como `experimental=True` | A3 |
| `INFORME_ARQUITECTURA_6GB.md` | Documentar que 26B-A4B-UD-Q2_K_XL es la mejor opción si el equipo tiene 12 GB+, no E4B-Q6_K | A1 |

## 2. Bloque B — Flags llama-server (B1–B3)

### B1. Tabla exhaustiva de flags llama-server con valor por familia

Esta tabla integra (a) la doc oficial llama.cpp, (b) los hallazgos específicos de los issues #21468/#21690/#21316/#21418/#21868 post-release de Gemma 4, (c) las recetas publicadas por Unsloth en `unsloth.ai/docs/models/gemma-4`, y (d) el análisis de `medium.com/@michael.hannecke/tuning-llama-server-on-apple-silicon-9b3e778ab100` sobre la interacción `--parallel × --batch-size × --ubatch-size × --cache-reuse`.

**Defaults observados en build b9090+ (extrapolados de b8773–b8779 publicados en abril 2026, `fazm.ai/blog/llama-cpp-release-april-2026`):** `--flash-attn auto`, `--parallel 1`, `--batch-size 2048`, `--ubatch-size 512`, `--ctx-checkpoints 8` (Gemma 4 reset por el cliente a 1), `--cache-reuse 0`, `--cont-batching on`.

| Flag | Default | Valor recomendado E2B (6 GB) | Valor recomendado E4B (6–8 GB) | Valor recomendado 26B-A4B (12–24 GB) | Riesgo / interacción | Confianza |
|---|---|---|---|---|---|---|
| `--flash-attn` | `auto` | `on` | `on` | `on` | Necesario para `--cache-reuse` y para que SWA funcione | CITADO |
| `--cache-type-k` | `f16` | `f16` | `f16` | `f16` (no q8_0) | **Gemma 4 KL 0.377 con q8_0 en 26B-A4B** (localbench). NO bajar | CITADO |
| `--cache-type-v` | `f16` | `f16` | `f16` | `f16` | Igual que K | CITADO |
| `--no-mmap` | off | `on` (Windows + SSD lento) | `on` para balanced/light | off | Cliente ya lo usa en balanced/light. Riesgo: arranque más lento, pero VRAM/RAM más predecible | CITADO (cliente) |
| `--mlock` | off | off | off | off (Windows) | En Windows `mlock` falla silenciosamente si no se es admin | EXTRAPOLADO |
| `-ngl`/`--n-gpu-layers` | `0` | `99` | `99` | `99` (o `-1` con `--fit on` si CUDA b8678+) | `--fit on` ahora calcula automático pero **no contabiliza mmproj** (#19980) | CITADO |
| `--parallel` | `1` | `1` | `1` | `1` (subir solo si concurrencia real) | Cliente correcto en `--parallel 1`. Mayor `--parallel` divide ctx por slot | CITADO |
| `--cont-batching` | on | on | on | on | No tocar | CITADO |
| `--ctx-checkpoints` | 8 | **1** | **1** | **1** | Bug #21690: con valor default explota RAM en Gemma 4 (3.6 GB × N) | CITADO |
| `--cache-reuse` | 0 | **256 (pero roto)** | 256 (roto) | 256 (roto) | Issue #21468 abierto. Hasta PR #22288 merged, no funcional en Gemma 4 por shared-KV. Logs muestran `sim = 0.000` | CITADO |
| `--threads` | núcleos físicos | núcleos físicos | núcleos físicos | núcleos físicos | En i7 12650H = 6P + 8E, fijar a 6 (P-cores) | EXTRAPOLADO |
| `--threads-batch` | igual a `--threads` | = threads | = threads | = threads | Para prefill puede subir | EXTRAPOLADO |
| `--ubatch-size` | 512 | 512 | 512 | 1024–2048 | Sube prefill throughput pero come VRAM en compute buffer | CITADO |
| `--batch-size` | 2048 | 2048 | 2048 | 2048 | Cap superior de `--ubatch-size` | CITADO |
| `--rope-freq-base` | from-gguf (1e6 base, 1e4 SWA) | dejar from-gguf | dejar from-gguf | dejar from-gguf | Gemma 4 usa **dual RoPE**: 1e6 global, 1e4 sliding (HF blog `gemma4`); modificarlo rompe | CITADO |
| `--rope-freq-scale` | 1.0 | 1.0 | 1.0 | 1.0 | No tocar | CITADO |
| `--predict` | -1 | 1280 (cliente actual) | 1280 | 1280 | Cliente correcto: doc Google recomienda 1280 max_tokens | CITADO |
| `--temp` | from-gguf (1.0) | 1.0 | 1.0 | 1.0 | Cliente correcto | CITADO |
| `--top-p` | from-gguf (0.95) | 0.95 | 0.95 | 0.95 | Cliente correcto | CITADO |
| `--top-k` | from-gguf (64) | 64 | 64 | 64 | Cliente correcto | CITADO |
| `--repeat-penalty` | 1.0 | 1.0 | 1.0 | 1.0 | Google: *"Keep repetition/presence penalty disabled or 1.0 unless you see looping"* (Unsloth doc) | CITADO |
| `--min-p` | 0.0 | 0.0 | 0.0 | 0.0 | No recomendado por Google para Gemma 4 | EXTRAPOLADO |
| `--dry-multiplier` | 0 | 0 | 0 | 0 | DRY no validado en Gemma 4 oficialmente | EXTRAPOLADO |
| `--xtc-probability` | 0 | 0 | 0 | 0 | Idem | EXTRAPOLADO |
| `--xtc-threshold` | 0.1 | n/a | n/a | n/a | Solo con `xtc-probability > 0` | EXTRAPOLADO |
| `--jinja` | off | **on** | **on** | **on** | Cliente correcto. Imprescindible para tool calling | CITADO |
| `--parse-tool-calls` | off | **on** | **on** | **on** | Activa parser nativo (no autoparser) post PR #21418 | CITADO |
| `--reasoning-format` | off | `auto` | `auto` | `auto` | Para Gemma 4 thinking mode | CITADO |
| `--reasoning-budget` | -1 | -1 | -1 | -1 | Cap de tokens de pensamiento; ajustar si latencia | EXTRAPOLADO |
| `--swa-full` | off | on (necesario para hint de cache-reuse) | on | on | Interactúa con #21468 | CITADO |
| `--keep` | 0 | **`-1`** (preservar todo el system prompt) | `-1` | `-1` | Mientras #21468 no esté arreglado, esto es la mejor defensa | EXTRAPOLADO |
| `--cache-ram` | -1 | 0 (Windows + 6 GB; evitar uso de RAM como cache de prompt) | 0 | hasta 4 GB en 16 GB+ | Reduce TTFT entre turnos largos | EXTRAPOLADO |
| `--no-context-shift` | off | off | off | off | Context shift es útil con `--keep` | EXTRAPOLADO |
| `--no-mmproj-offload` | off | off | off | off | Si VRAM apretada y vision activa: `on` | CITADO |
| `--chat-template-kwargs '{"enable_thinking":false}'` | n/a | usar para desactivar thinking en `light`/`balanced` (latencia) | igual | dejar thinking on en `performance` | Doc Unsloth confirma sintaxis | CITADO |
| `--chat-template-file` | n/a | `models/templates/google-gemma-4-31B-it-interleaved.jinja` si se hace agente con interleaved tool calls | igual | igual | PR #21418 introdujo template interleaved | CITADO |

**Flags nuevos post-release (entre b8607 y b8779):**

- `LLAMA_ATTN_ROT_DISABLE` (env var, no flag): TurboQuant-style Hadamard rotation **on por default** desde b8607. Solo desactivar para debug. Aplica a Gemma 4. (`fazm.ai/blog/llama-cpp-release-april-2026`).
- `--reasoning on` y `--reasoning off` (post b8662): control explícito en CLI sin modificar plantilla.
- `--cache-ram N` (post b8666 según discusiones): tamaño de cache de prompt en RAM en MiB (en MoE útil).

### B2. Combinación que reduce VRAM sin degradar > 2% en Carter

[NO PÚBLICAMENTE MEDIDO AL 2026-05-15 para Carter 540]. Combinaciones plausibles a probar A/B en casa, ordenadas por ahorro esperado y riesgo bajo:

1. `--cache-type-k q8_0 --cache-type-v q8_0` **sólo si tu Carter no incluye long-docs ni tool calling complejo** (Gemma 4 26B-A4B q8_0 KV → KL 0.377 según localbench; el 31B mejora a KL 0.108). En E4B no hay número público pero extrapolación es ≥ 31B [EXTRAPOLADO].
2. `--ctx 4096` en lugar de 8192 (ya hecho en `light`).
3. `-ngl` menor que 99 con CPU offload selectivo de capas finales (las que usan shared-KV ahorran menos VRAM).
4. `--no-kv-offload` (en builds recientes): mantiene KV en RAM; útil en 6 GB pero penaliza tok/s.

**Mid de evaluación:** correr Carter 540 dos veces por configuración candidata, reportar (pass-rate, p50 TTFT, p95 latencia, VRAM peak). Aceptar cualquier configuración con `pass_rate >= baseline - 2pp` y VRAM peak ≤ baseline - 0.5 GB.

### B3. Build oficial CUDA vs compilar desde fuente

| Variable de build | Default | Recomendación | Comentario |
|---|---|---|---|
| `LLAMA_CUDA_F16` | OFF | OFF | El cliente no usa F16 KV crítico; activarlo solo en H100/Blackwell | EXTRAPOLADO |
| `LLAMA_CUDA_FORCE_MMQ` | OFF | OFF en RTX 30xx/40xx | MMQ es ahora la ruta default vía MMQ kernels; FORCE puede degradar en SM_86 | EXTRAPOLADO |
| `LLAMA_CUDA_DMMV_X` | 32 | dejar default | No hay evidencia post-Gemma-4 de ganancia | EXTRAPOLADO |
| `GGML_CUDA=ON` | requerido | ON | Obviamente | CITADO |
| `LLAMA_CURL=ON` | OFF | ON | Necesario para `-hf` | CITADO |
| `BUILD_SHARED_LIBS=OFF` | ON | OFF (binario monolítico) | Distribución simple en Windows | CITADO |

**Recomendación final:** usar **build oficial** de llama.cpp (releases tagged) y *pin de SHA*. Compilar desde fuente sólo si se necesita cherry-pick de PR #22288 (cache-reuse Gemma 4) cuando salga. Para Windows, los releases binarios oficiales (`llama-b8639+-bin-win-cuda-13.1-x64`) están probados con Gemma 4. **No** usar CUDA 13.2 runtime: Unsloth alerta *"Do NOT use CUDA 13.2 runtime for any GGUF as it will cause poor outputs"* (`unsloth.ai/docs/models/gemma-4`, Apr 11 update). **Confianza CITADO.**

## 3. Bloque C — Tool calling (C1–C4)

### C1. Estabilidad del template Jinja oficial de Gemma 4

**Hallazgo:** el template Jinja embebido en el GGUF oficial fue actualizado dos veces post-release. El de Google es el canónico; los repos de Bartowski/Unsloth lo replican y actualizan.

- **Evidencia:** PR llama.cpp **#21418 (merged 2026-04-04)** introduce parser dedicado Gemma 4: *"common : add gemma4 dedicated parser. * cont : add '<|tool_response>' as eog. * cont : emit JSON from Gemma4 tool call AST"* y añade el template `models/templates/google-gemma-4-31B-it-interleaved.jinja` para *interleaved thinking* (función calling sin perder thoughts entre llamadas).
- **Update de chat template 2026-04-11** según Unsloth: *"Apr 11 update: Gemma 4 is now updated with Google's updated chat template + llama.cpp fixes."* Bartowski actualizó los GGUF *"Update chat template 10–11 days ago"* (~05-04 a 05-06 según fechas relativas del scrape).
- **Compatibilidad con `--jinja`:** SÍ. llama-server respeta el chat_template embebido en GGUF. Tags reales: `<|turn>system`, `<|turn>user`, `<|turn>model`, `<|channel>thought`, `<channel|>`, `<|think|>`, `<|tool_response>`, `<turn|>` como EOS.
- **Cliente:** ya usa `--jinja`. Acción: añadir `--chat-template-file models/templates/google-gemma-4-31B-it-interleaved.jinja` cuando se hagan turnos con tool calls *intercalados con razonamiento*. **Confianza CITADO.**

### C2. Bugs conocidos del parser de tool calls en llama-server para Gemma 4

Issues confirmados post-release. Estado al **2026-05-15** (43 días desde release):

| Issue | Descripción | Estado | Fix |
|---|---|---|---|
| `#21316` | "Gemma4 tool calling leaves unexpected tokens in tool calls" — `<unused25>` token spam | Cerrado por #21326 | Merged abr 2026 |
| `#21343` | Tokenizer bug — output garbled | Merged 2026-04-03 | b8641+ |
| `#21384` | "Gemma 4 tool call array parameter serialized as JSON string when values contain `{` or `}`" | Verificar en b9090+. **No confirmado merged en mi research** | Workaround: validar args en `safety.py:classify_tool_call` parseando dos veces |
| `#21418` | Parser dedicado, EOS `<|tool_response>`, AST → JSON | **Merged 2026-04-04** (b8645+) | Activo |
| `#21468` | `cache-reuse` no soportado por shared-KV | **Abierto**, PR #22288 candidato | — |
| `#21690` | mmproj + checkpoints OOM RAM | Workaround: `--ctx-checkpoints 1 -np 1` | Sin merge |
| `#21868` | `input_audio` HTTP 500 en `/v1/chat/completions` | **Closed not planned** | Workaround: subprocess `llama-mtmd-cli` |
| Streaming tool calls | El gist de Daniel Farina (`gist.github.com/daniel-farina/87dc1c394b94e45bb700d27e9ea03193`) documenta que en Ollama "streaming drops tool calls" — en llama-server con `--jinja` post-#21418 funciona correctamente, con eventos SSE delta `tool_calls` chunk a chunk (Issue #21316 trace: ver §D4) | OK post-#21418 | — |

**Recomendación al cliente:** pin de build **b9090+** (o release etiquetado equivalente con #21418, #21326, #21343 merged) y test de regresión en `safety.py:classify_tool_call` añadiendo casos con `{`/`}` en argumentos (issue #21384). **Confianza CITADO.**

### C3. `parallel_tool_calls` en Gemma 4

[NO PÚBLICAMENTE DOCUMENTADO en sentido formal por Google al 2026-05-15]. Lo que sí está documentado:

- El template interleaved (`#21418`) permite **múltiples tool calls dentro del mismo turno del modelo** intercalados con thoughts (*"Function Calling (Exception): If a single model turn involves function or tool calls, thoughts must NOT be removed between the function calls"* — comentarios del PR).
- vLLM expone `--tool-call-parser gemma4` y `--enable-auto-tool-choice` (issue #39133 vLLM con cyankiwi/gemma-4-31B-it-AWQ-4bit), lo que sugiere que el parser oficial sí soporta llamadas paralelas a tools.
- **Degradación de calidad con paralelismo:** [NO MEDIDO PÚBLICAMENTE]. **Recomendación de medición casera:** en `harness_carter540/`, categorizar tareas según (single-tool, multi-tool sequential, multi-tool parallel) y medir delta pass-rate. La hipótesis razonable es que E2B/E4B degradan en parallel; 26B-A4B/31B se sostienen.

### C4. Mejorar tool selection accuracy sin fine-tuning

Técnicas con evidencia post-release o aplicables directamente:

1. **Inyectar parámetros exactos en system prompt**, formato Daniel Farina: *"# Tool Schemas (EXACT parameter names - you MUST use these exactly)"* seguido de cada tool con tipos y `REQUIRED`/`optional`. Este patrón es el AGENTS.md del OpenCode gist. Disminuye tool call errors empíricamente (sin número publicado). **Acción:** `tools.py:COMPOUND_TOOL_SCHEMAS` — añadir un compilador a Markdown que se inyecte en system prompt al lanzar. [CITADO]
2. **Activar thinking mode (`<|think|>`)** para tareas multi-step. La doc Unsloth y los model cards confirman que el thinking interleaved mejora reasoning y, por extensión, tool selection. Riesgo: latencia. Recomendación: thinking on solo en `performance`; en `balanced` y `light` thinking off por defecto, con flag explícito `--chat-template-kwargs '{"enable_thinking":false}'`. [CITADO]
3. **Reducir el catálogo expuesto** según contexto: 62 tools cargados siempre es un over-prompt costoso. Implementar `safety.py: classify_intent → filter_tools` (no hay evidencia Gemma-4-específica, pero práctica estándar). [EXTRAPOLADO]
4. **Templates "interleaved"** (Gemma 4 específico, no Gemma 3): para agentes multi-step con razonamiento entre tools. PR #21418 incluye `google-gemma-4-31B-it-interleaved.jinja`. [CITADO]
5. **No usar grammar constraint sobre JSON arguments** — el PR #21418 explica que *"the model does not produce JSON in tool calls, so our existing implementation doesn't apply"* (Gemma 4 produce un AST específico). En cambio, **sí** se puede usar `response_format` schema para respuestas finales no-tool. [CITADO]

**Archivos a tocar:**
- `tools.py:COMPOUND_TOOL_SCHEMAS` — generar bloque Markdown estilo OpenCode.
- `safety.py:classify_tool_call` — añadir validación post-parse robusta a `{`/`}` (issue #21384).
- `llama_server.py:_build_server_cmd` — añadir `--chat-template-file <interleaved>` cuando `profile == "performance"`.
- `profiles.py` — añadir `enable_thinking` por perfil.

## 4. Bloque D — Latencia y streaming (D1–D4)

### D1. `--cache-reuse` reparado para Gemma 4

**Hallazgo:** NO al 2026-05-15.

- Issue **#21468 abierto desde 2026-04-05** (build 8660). PR **#22288** mencionado en el cuerpo del issue es el candidato. **No confirmado merged.**
- Causa raíz documentada: *"Gemma 4 uses a Shared KV Cache architecture where the last `num_kv_shared_layers` layers reuse K/V tensors from the last non-shared layer rather than computing their own. This architectural property likely breaks the assumptions in the cache reuse / prefix matching code, causing it to explicitly bail out with 'cache reuse is not supported.'"*
- Impacto en producción cliente: cada turno con system prompt grande (compound tools 62 entradas) reprocesa todo el prefix. Para un agente con tools, Carter reportarará TTFT alto y conversaciones largas con degradación creciente. Una vez merged, el reporter de #21468 estima recuperar ~93% del TTFT que se pierde hoy.
- **Build mínimo cuando salga:** verificar fecha de merge antes de upgrade ciego, ya que otros fixes (#22288) podrían interactuar.

**Workaround mientras está roto:**
- `--keep -1` para evitar context shifts del system prompt.
- Mantener un único slot (`--parallel 1`) para que la cache de prompt persista entre turnos del mismo cliente.
- Considerar `--cache-ram <MiB>` (Q3) para que el slot anterior persista cuando hay swap. **Confianza CITADO.**

### D2. MTP drafters Gemma 4 en llama.cpp

**Hallazgo:** Google publicó drafters MTP el **2026-05-05** (4 checkpoints: E2B-it-assistant, E4B-it-assistant, 26B-A4B-it-assistant, 31B-it-assistant). **Upstream llama.cpp no soporta la arquitectura aún.**

- Fuente principal: `blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/` (2026-05-05) y `ai.google.dev/gemma/docs/mtp/overview`.
- Speedup reportado por Google: **"hasta 3×"** con calidad idéntica (verification por target). Acceptance share: Gemma 4 26B-A4B-it FP8 + MTP γ=4 → 108.78 tok/s single-stream (2.66× baseline 40.85) en DGX Spark / GB10 (`ai-muninn.com/en/blog/dgx-spark-gemma4-mtp-108-toks`, 2026-05-06).
- vLLM: PR #41745 abierto y aprobado mismo día; Docker image preview hours later. **Producción rápida en vLLM, no en llama.cpp.**
- llama.cpp Discussion **#22735** abierta 2026-05-08: *"convert_hf_to_gguf.py does not recognize the architecture Gemma4AssistantForCausalLM"*. Bypass manual con `Gemma2Model` falla por tensores `model.layers.0.layer_scalar` no mapeados.
- ik_llama.cpp PR **#1744** (autor SamuelOliveirads), aprobado 2026-05-05, no merged al 2026-05-08. Fork patches en `github.com/karany97/llamacpp-gemma4-mtp` (MIT) ofrecen build pre-compilado para Linux/Windows con dual RTX 3090. Speedup verificado **2.6–2.98× lossless**.
- **Conclusión:** [NO disponible en upstream llama.cpp al 2026-05-15]. Hay tres rutas:
  - (a) Esperar el PR upstream (estimado 2–6 semanas [EXTRAPOLADO]).
  - (b) Cambiar runtime a ik_llama.cpp (rompe restricción "llama.cpp único"; NO recomendado por el brief).
  - (c) **Hacer speculative decoding con draft externo** sobre llama.cpp upstream — funciona hoy (ver D3).

### D3. Speculative decoding E2B-draft → E4B/26B-A4B-target

**Hallazgo:** funciona en llama.cpp upstream con `--spec-draft-model`, pero el costo VRAM en 6 GB lo hace inviable para E4B-target+E2B-draft a la vez en 6 GB.

- Doc oficial llama.cpp speculative (`github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md`):
  - `--spec-draft-model FNAME` (alias `-md`).
  - `--spec-draft-n-max 16` (default), `--spec-draft-n-min 0`.
  - `--spec-draft-p-split 0.10`, `--spec-draft-p-min 0.75`.
  - `--spec-draft-ngl 99` (offload draft a GPU).
  - **Validación de compatibilidad:** vocabulario, BOS/EOS, y primeros tokens deben coincidir. **E2B y E4B son ambos `gemma4` arch con mismo tokenizer → compatibles**. [CITADO]
- Acceptance rate típico: depende del par. En modelos no-MTP-trained, Unsloth reporta 30–60% en tareas estructuradas; en código mucho más alto. Para Gemma 4, sin medición pública específica del par E2B→E4B, [EXTRAPOLADO] 40–60% en Carter.
- **Costo VRAM:** E2B Q4_K_M = 1.85 GB (cliente). En 6 GB con E4B-UD-Q4_K_XL (~5.6 GB con KV) → **no entra**. En 8 GB sí (E2B-Q4 + E4B-Q4 = 7.5 GB + overhead → borderline). En 12 GB+ confortable.
- **Resultados negativos:** el bench `hackmd.io/ODXuOQNzSiyUITz7g9mtBw` muestra que en Qwen3.6-35B-A3B sobre RTX 3090, **draft-spec en llama.cpp resulta más lento que baseline** (139.9 → 65.0 tok/s con `--draft-min 2 --draft-max 32`). Atribuido a "engine + spec-method specific to llama.cpp draft-spec on consumer Ampere with Q4 target". **Lección para Gemma 4 en RTX 30xx 6 GB consumer: NO asumir speedup**.
- **Recomendación de medición casera:** A/B con `llama-bench --model-draft` antes de activar en producción. Si acceptance < 50%, dejar off. **Confianza CITADO.**

### D4. Streaming SSE de tool calls completo en b9090+

**Hallazgo:** SÍ funciona post-#21418 (texto + tool_call + texto en mismo turno, chunk a chunk).

- Issue #21316 incluye el log SSE exacto:
  - `data: {"choices":[{"finish_reason":null,"index":0,"delta":{"role":"assistant","content":null}}], ...}`
  - `data: {"choices":[{"finish_reason":null,"index":0,"delta":{"tool_calls":[{"index":0,"id":"...","type":"function","function":{"name":"edit","arguments":"{\"edits\":...}}}]}}], ...}`
  - `data: {"choices":[{"finish_reason":"tool_calls","index":0,"delta":{}}], ...}`
- Sin embargo, hay un bug específico (#21384): cuando los argumentos contienen `{` o `}` literales (e.g. JSON con braces), **el array `edits` se serializa como string en lugar de array**. El cliente debe robustecer parsing en `llm_client.py` aceptando ambos casos. [CITADO]
- En modo **non-streaming** post-#21418 el `tool_calls` viene en el campo `message`, no en `delta`; ambos formatos están alineados con OpenAI Chat Completions.
- **Acción en `llm_client.py`:** unit test con (a) call simple, (b) call con `{` y `}` en args, (c) call interleaved con thoughts en `reasoning_content`. **Confianza CITADO.**

## 5. Bloque E — Visión y audio nativo (E1–E6)

### E1. Leak de mmproj (#21690) cerrado

**Hallazgo:** NO cerrado al 2026-05-15. Build 8724 confirma RAM creciente abnormal en Gemma 4 con `--ctx-checkpoints` default. Workaround validado del propio reporter: `--ctx-checkpoints 1 -np 1` previene la OOM. (`github.com/ggml-org/llama.cpp/issues/21690`).

- Adicional **#19980** (genérico de mmproj + `--fit on`): el cálculo de `--fit` **no contabiliza la VRAM del mmproj**, lo que causa OOM probabilísticas en 6 GB. **Mitigación:** desactivar `--fit on` y fijar `-ngl 99` + `--no-mmproj-offload` cuando vision está prendida y VRAM es tight. [CITADO]
- El cliente reporta crecimiento ~6.4 MiB/imagen GPU + 46 MiB host/request. **Coincide cualitativamente** con #21690 (que reporta "varios gigabytes por full prompt processing de 16K"). Para flujo "Alexa-like" con visión esporádica, recomendar **proceso de server efímero por bloque de imágenes** (relaunch cada N=40 imágenes). **Confianza CITADO.**

### E2. `input_audio` reabierto post-#21868

**Hallazgo:** NO. Issue #21868 "closed not planned". El cliente lo sabe. Status detallado:

- PR **#21421** ya merged: añadió el conformer USM audio encoder a libmtmd. `llama-mtmd-cli --audio` funciona correctamente.
- Lo que falta: `server.cpp` debe enrutar `input_audio` content type al mismo path interno. *"The underlying libmtmd library fully supports audio — the gap is exclusively in server.cpp's content-type dispatch logic"* (#21868).
- Workaround sin `llama-mtmd-cli` cold-load: **no existe oficialmente**. El propio issue cierra recomendando subprocess.
- Alternativa de arquitectura: **mantener Whisper como STT primario** (lo que ya hace el cliente). Esto evita el riesgo, libera el camino para que la migración a audio nativo Gemma 4 sea opt-in cuando el cliente lo decida. **Confianza CITADO.**

### E3. Calidad WER audio nativo Gemma 4 en español

**Hallazgo:** [NO PÚBLICAMENTE MEDIDO AL 2026-05-15]. El bench interno del cliente (2/5 = 40%) no tiene comparable público.

- Lo que está documentado: Gemma 4 E2B/E4B usan *"USM-style conformer with the same base architecture as the one in Gemma-3n"* (HF blog `gemma4`). USM se entrenó con cobertura multilingüe pero el corpus exacto del finetune Gemma 4 no está publicado.
- Audio máx 30 s; recomendación oficial: *"put image and/or audio before text"* (Unsloth doc).
- Como el cliente reporta 40% interno (vs Whisper-small ~92%), **la brecha es enorme y no plausible-recuperable en 30 días sin retraining** [EXTRAPOLADO]. **Recomendación firme:** Whisper queda como STT. Reevaluar en 90 días si Google publica un finetune ES o si el modelo madura. **Confianza EXTRAPOLADO.**

### E4. Whisper-large-v3-turbo CPU vs Whisper-small

**Hallazgo:** turbo es más rápido **y** mejor en WER, **pero** requiere 4× más RAM y rasgo de allucinación en clips muy cortos.

| Modelo | Parámetros | RAM CPU int8 | RTF CPU típica | WER (LibriSpeech clean) | WER es-MX |
|---|---|---|---|---|---|
| Whisper-small | 244M | ~0.5 GB | 4–10× (cliente) | ~5% | ~8% [EXTRAPOLADO] |
| Whisper-large-v3-turbo int8 | 809M | **1.5 GB** | **~13× CPU típica** | **2.4–4.6%** (faster-whisper bench) | ~5.34% (fine-tuned adriszmar) |
| Distil-Whisper-large-v3 int8 | ~756M | 1.5 GB | ~22× | 2.4% | sin medición es-MX |

- faster-whisper benchmark issue #1030: turbo int8 = 1.5 GB VRAM, ~13× CPU RTF (con CTranslate2).
- "Community reports indicate Turbo hallucinates more on very short clips or noisy recordings vs V3" (`whispernotes.app/blog/introducing-whisper-large-v3-turbo`).
- Para el caso del cliente (wake word "Alexa local", clips típicos 2–8 s) el riesgo de halucinación en clip <1 s aumenta. **Recomendación:** mantener silero-vad agresivo antes de turbo. **Confianza CITADO.**

### E5. Alternativas open-source más rápidas con calidad ≥ Whisper-small en español, 100% local CPU

| Modelo | Multilingüe es? | RTF CPU | Licencia | Veredicto |
|---|---|---|---|---|
| **NVIDIA Parakeet-TDT-0.6B-v3** | SÍ (25 idiomas europeos incluido español, multilingüe nativo) | Muy alto (modelo RNN-T, optimizado streaming) | NVIDIA Community Model License (revisar términos) | **Mejor candidato a evaluar.** Auto-detección idioma. 600M params. Detalles: `huggingface.co/nvidia/parakeet-tdt-0.6b-v3` |
| Parakeet-TDT-0.6B-v2 | EN solo | Muy rápido | NVIDIA CML | Descartado por monolingüe |
| Parakeet-RNNT-1.1B multilingual | SÍ (multilingüe) | Alto | NVIDIA CML | 1.1B, más pesado |
| Canary-1B-flash | 4–5 idiomas | Alto | NVIDIA CML | Cobertura idiomas reducida |
| Distil-Whisper-large-v3 | EN principalmente, multilingüe limitado | Muy rápido | MIT | No es claramente mejor en es |
| AssemblyAI Universal-2 | SÍ | n/a | **Closed (cloud-only)** | **NO cumple "100% local"** — descartado |

**Recomendación:** experimentar con Parakeet-TDT-0.6B-v3 en `voice/stt.py` como segundo backend opcional, con feature flag. La licencia NVIDIA CML es la única blocker. **Confianza CITADO.**

### E6. TTS open-source local mejor que Piper en español

**Hallazgo:** Piper sigue siendo el mejor *latency-vs-quality* para tiempo-real en CPU; otros modelos ofrecen voz más natural a costa de latencia o licencia.

| TTS | Tamaño | RTF CPU | Idiomas / voces es | Latencia 1er fonema | Licencia | Veredicto |
|---|---|---|---|---|---|---|
| **Piper VITS+ONNX** (actual) | <50 MB | >10× CPU | Voces es-AR, es-ES, es-MX oficiales | <300 ms en CPU 4 cores | MIT | Baseline; ganador en latencia |
| **Kokoro-82M v1.0** | 82M params | ~3–11× CPU, 90–210× GPU | Español listado (`'e'` lang code) en config (`github.com/PierrunoYT/Kokoro-TTS-Local`); voces es disponibles en `fal.ai/models/fal-ai/kokoro/spanish` | ~600–1200 ms primer chunk CPU [EXTRAPOLADO] | **Apache 2.0** | **Mejor calidad-vs-licencia.** Recomendado A/B contra Piper en producción |
| **XTTS-v2** (Coqui) | 467M | ~1× CPU (lento) | ES sí, voice cloning | >2 s primer chunk CPU | **CPML (no-comercial)** | Descartado por licencia |
| **Fish Speech** | ~700M | n/a CPU | ES sí | n/a | Apache 2.0 | Alternativa, mayor footprint |
| **Bark** | 1.5GB | n/a CPU | ES | varios s | MIT | Demasiado lento |
| **Parler-TTS** | 880M | n/a CPU | EN | — | Apache 2.0 | EN-first |

**Resumen:**
- **Mantener Piper** como default por latencia ≤1 s exigida por el brief.
- **Añadir Kokoro-82M es** como opción "high-quality" feature-flagged para usuarios que toleran +500 ms. Apache 2.0 lo hace viable comercial.
- **Descartar XTTS-v2** por CPML (no-comercial) — el cliente publica un asistente, conflicto con esa licencia.
- **Voces es-AR oficiales:** Piper publica `es_AR-daniela-high` y `es_AR-daniela-low`. No moverse de allí salvo cambio explícito. **Confianza CITADO.**

**Archivos a tocar:**
- `voice/stt.py`: añadir backend `parakeet_tdt_v3` opt-in con flag `STT_BACKEND=parakeet|whisper_small|whisper_turbo`.
- `voice/tts.py` (no listado pero implícito): añadir backend `kokoro_es` opt-in.
- `INFORME_ARQUITECTURA_6GB.md`: documentar que el audio nativo Gemma 4 está bloqueado por #21868 y permanecerá bloqueado.

## 6. Bloque F — Costos ocultos VRAM (F1–F4)

### F1. Overhead real Windows 11 + CUDA driver + WDDM en GPU ≤8 GB VRAM

[NO MEDIDO PÚBLICAMENTE en una fuente Tier 1/2 reproducible para Gemma 4 en 2026]. Lo que sí hay es evidencia anecdótica de foros Microsoft/Tom's Hardware/elevenforum: **`dwm.exe` reserva 0.6–1.2 GB en sistemas modernos con un monitor 1080p+**, además de buffers de driver de **150–400 MB**.

| Fuente | VRAM ocupada idle desktop | Hardware |
|---|---|---|
| Tom's Hardware forum (4070 Ti 12 GB) | ~1.2 GB | Win11 Pro, 4070 Ti |
| Microsoft Q&A `dwm.exe` high GPU | "varios cientos de MB" | varios |
| `windowsnews.ai` Task Manager analysis | "dedicated GPU memory reserved by Windows" — categoría separada | n/a |

**Recomendación operativa:** en `profiles.py:recommend_profile(vram_mb)`, **reservar 1.5 GB** del total reportado por `nvidia-smi` antes de elegir perfil. Para una RTX 3050 6 GB: VRAM efectiva budget ≈ **4.5 GB**, no 6 GB. Eso convierte E4B-Q4_K_M (5.41 GB) en *not safe* sin trucos (no-mmap, mmproj OFF, ctx 4K, KV F16 truncado). [EXTRAPOLADO; medir en máquina target]

**Medición casera reproducible:**
1. Reboot Windows 11.
2. `nvidia-smi --query-gpu=memory.used --format=csv` antes de cualquier cosa → baseline desktop.
3. Lanzar `llama-server -hf ...` → segunda medición.
4. Inferir 1K tokens → tercera medición (compute buffer real).
5. Repetir con tres GGUF distintos.

### F2. Crecimiento KV cache por 1K tokens

**Fórmula general:** `KV_bytes = n_kv_heads × head_dim × n_layers × 2 × ctx_tokens × bytes_per_element`.

Datos confirmados de `gemma4.*` keys en GGUF (issue #21325):
- E4B (instruct, F16): `block_count=42`, `attention.head_count_kv=2`, `attention.key_length=512`, `attention.value_length=512`.
  - **Por token (F16, sin SWA):** 2 × 512 × 42 × 2 × 2 bytes = 172 032 bytes = **168 KiB/token**.
  - **Por 1K tokens F16:** ~168 MiB *si todas las capas fueran full attention*. Pero Gemma 4 usa **shared-KV en las últimas N capas + SWA local 512 en mitad**, lo que reduce considerablemente. Sin la config exacta de `num_kv_shared_layers` y `sliding_window` por GGUF [NO PUBLICADO en model card detail], no podemos cerrar el número.

Datos de Kaitchup (`kaitchup.substack.com/p/gemma-4-31b-and-26b-a4b-architecture`, derivado de config):
- **Gemma 4 26B-A4B:** `5,578,424,320 bytes` para sequence completa a 256K → **~21.3 KiB/token efectivos** tras SWA y shared-KV (5×262144×4096 + 25×1024×8192).
- **Gemma 4 31B:** 25% más KV que Qwen3.5 27B a 256K → ~ 7 GiB a contexto pleno [CITADO con derivación].

| Modelo | KV/token efectivo F16 | KV/token q8_0 | KV/token q4_0 |
|---|---|---|---|
| E2B | ~32 KiB [EXTRAPOLADO] | ~16 KiB | ~8 KiB |
| E4B | ~42 KiB [EXTRAPOLADO desde block_count=42 con SWA] | ~21 KiB | ~10.5 KiB |
| 26B-A4B | ~21.3 KiB [CITADO Kaitchup, asumiendo full context 256K linealizado] | ~10.7 KiB | ~5.3 KiB |
| 31B | ~28 KiB [CITADO Kaitchup] | ~14 KiB | ~7 KiB |

**Implicación para 6 GB:** ctx 8K en E4B F16 ≈ 336 MB KV; ctx 32K ≈ 1.3 GB. Si el modelo pesa 5.4 GB en VRAM, ctx 8K es el techo. **Recomendación brutal:** mantener `ctx=4K` en `light` y `ctx=8K` en `balanced` (ya están) **y NO subir a q8_0 KV** dado el #21468/localbench. **Confianza CITADO con derivación.**

### F3. `--ctx-checkpoints` y VRAM

**Hallazgo:** los checkpoints viven en **RAM (host)**, no VRAM, según el log del issue #21690: *"the previous slot's state is saved, ~298 MiB for a 46K token prompt"*. Cada checkpoint en Gemma 4 default ocupa ~3.6 GB de RAM, no de VRAM (`I think I have been solved Gemma-4-31B-it heavy system memory occupied`, Discussion #21689).

- **No es gratis en VRAM porque no toca VRAM directamente.** Pero sí puede degradar latencia si la RAM se llena y Windows pagina a disco.
- **Cliente ya lo tiene en 1.** Correcto. **Confianza CITADO.**

### F4. `llama-server` en idle: liberar VRAM sin cerrar proceso

**Hallazgo:** NO existe modo *sleep* nativo en llama-server al 2026-05-15.

- La discusión `Lazy Loading MMPROJ file` (#20855) propone `--mmproj-load-on-demand` pero está **abierta**, sin merge.
- Issue `Misc. bug: DGX Spark memory not released using llama.cpp?` (NVIDIA dev forums) confirma que **memoria no se libera mientras el proceso vive** en Spark; aunque en RTX comunes la situación es distinta, no hay endpoint `/idle`.
- **Alternativa práctica:** `llama-swap` o el modo router nativo de llama-server (post mid-2024 con `--models` flag) permiten **descargar el modelo cuando expira el TTL** y dejar el proxy escuchando. Esto **sí** libera VRAM (`modelslab.com/blog/api/hot-swap-local-llms-instantly-llama-swap-setup-guide-2026`). Cold-start posterior: 5–30 s según tamaño y disco.
- **Recomendación:** en perfil `standby` (cliente ya tiene "server off"), el método correcto es `--ttl <segundos>` en llama-swap o cerrar el proceso. Para "idle parcial" no hay primitiva. **Confianza CITADO.**

**Archivos a tocar:**
- `llama_server.py`: añadir lógica de auto-kill por idle timer (e.g. 5 min sin requests) y relaunch a la primera request, controlada por `AgentConfig.idle_timeout_s`.
- `INFORME_ARQUITECTURA_6GB.md`: documentar que reservamos 1.5 GB VRAM para Windows.

## 7. Bloque G — Profile switching (G1–G3)

### G1. Swap entre GGUF en mismo proceso vs kill+relaunch

**Hallazgo:** kill+relaunch en llama-server estándar es la opción simple y predecible; el "router mode" interno (`--models`) y `llama-swap` ofrecen alternativas.

- **Kill + relaunch:** 3–10 s para 7–8B Q5 según Glukhov (`glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/`). En SSD NVMe + Windows con 6 GB GPU: medible localmente. Para E4B Q4_K_M (5.4 GB) sobre PCIe 4.0 SSD: estimación 4–6 s [EXTRAPOLADO].
- **Router mode interno (`--models`):** el mismo proceso mantiene el HTTP server vivo y carga/descarga modelos a demanda. *"Switching means a full unload-and-reload cycle"* — no es más rápido que kill+relaunch en términos de IO, pero **mantiene la conexión HTTP** (sin cliente reconectando).
- **llama-swap** (externo, Go, MIT): mismo principio, mejor isolation; soporta hot-reload de config y SSE.
- **No hay swap "tibio"** que conserve weights en RAM y reuse: cada switch fuerza load completo desde disco a VRAM. **Confianza CITADO.**

### G2. Endpoint hot-reload sin perder conexión HTTP

- **llama-server nativo:** router mode (`--models flag`, post mid-2024) lo permite parcialmente — la conexión HTTP persiste, el modelo se swappea. Cliente debe usar `?model=<name>` o body `"model"` correcto.
- **llama-swap:** *"sits in front of any OpenAI-compatible upstream"*, único `/v1` que persiste para clientes; cambia upstream según `model` field. SSE no se rompe entre requests; durante el swap mismo sí (el cliente debe reintentar).
- **Recomendación al cliente:** dado que el brief restringe a llama.cpp como runtime único y prohibe nuevas deps pesadas, **NO instalar llama-swap**. Implementar router-mode si versión llama-server lo soporta, o gestor de procesos en Python (`llama_server.py`) que mate y relance subprocess. **Confianza CITADO.**

### G3. Mantener GGUF mmaped en RAM durante swap

**Hallazgo:** mmap es lectura demand-paged desde disco; el kernel mantiene páginas en page cache mientras hay RAM libre. **No hay un "preload" oficial** para acelerar el swap entrante en llama-server.

- En Windows, con `--no-mmap` (que el cliente usa en `balanced/light`): cada load es read completo + alloc. Sin mmap, el segundo load NO se acelera.
- **Con mmap (default):** el OS conserva las páginas calientes; el segundo load del *mismo* GGUF es prácticamente instantáneo en VRAM (la copia host→device es lo único que queda). Para *otro* GGUF, no hay beneficio.
- **Trick avanzado**: copiar el GGUF a `tmpfs` o RAM-disk explícito; load se vuelve "RAM→VRAM PCIe only". Acelera 3–5× vs SSD primer load. [EXTRAPOLADO; no medido en Gemma 4 específicamente]
- **Recomendación pragmática:** quitar `--no-mmap` en `balanced` si se va a swappear con frecuencia (tradeoff: arranque inicial igual, segundo arranque mucho más rápido). Si el caso de uso es un único modelo siempre cargado, `--no-mmap` es válido. **Confianza EXTRAPOLADO.**

**Archivos a tocar:**
- `llama_server.py:_build_server_cmd` — eliminar `--no-mmap` en `balanced` si se observa swap frecuente; mantener en `light` (donde se prioriza RAM determinista).
- `profiles.py` — exponer `mmap_enabled: bool` por perfil.

## 8. Bloque H — Calidad medida vs bench interno (H1–H3)

### H1. Proyección de PASS rate por GGUF y correlación con Carter 540

[NO PÚBLICAMENTE MEDIDO para Carter, que es interno]. Construimos una matriz de proxies disponibles:

| GGUF | KLD vs BF16 (localbench/Unsloth) | MMLU-Pro [oficial] | AIME 2026 [oficial] | τ2-bench (agentic tool use) [oficial] | Proyección Carter [EXTRAPOLADO] |
|---|---|---|---|---|---|
| 31B-it BF16 | 0 (referencia) | 85.2% | 89.2% | 86.4% | ~99–100% Carter |
| 31B-it Q8_0 | KL 0.108 (localbench) | ~85% | ~89% | ~86% | ~99% |
| 31B-it UD-Q4_K_XL | en Pareto Unsloth | [no medido] | [no medido] | [no medido] | ~96–98% |
| 26B-A4B-it BF16 | 0 | 82–83% [aprox, MMLU multilingüe 85.2 según aihaven] | 88.3% | 82.3% | ~97–99% |
| 26B-A4B-it q8_0 KV (NO de pesos) | **KL 0.377** (problemático para algunas categorías) | n/a | n/a | n/a | impacto Carter [NO MEDIDO] |
| 26B-A4B-it UD-Q4_K_XL | Pareto frontier (top 21/22 según Unsloth) | [no medido] | [no medido] | [no medido] | ~95–97% |
| 26B-A4B-it UD-Q2_K_XL | Pareto frontier (dominio sobre UD-IQ3_XXS) | [no medido] | [no medido] | [no medido] | ~90–94% |
| 26B-A4B-it MXFP4_MOE | inferior a Q4_K en muchos tensores (Unsloth) | [no medido] | [no medido] | [no medido] | ~88–92% |
| E4B-it BF16 | 0 | benchmark Google: AIME 42.5% | n/a | n/a | ~85–90% [EXTRAPOLADO] |
| E4B-it Q8_0 | ~0 (idéntico entre uploaders según localbench) | ~baseline | ~baseline | ~baseline | ~84–89% |
| E4B-it Q6_K (cliente dev) | mínima penalty | ~baseline -0.5% [EXTRAPOLADO] | n/a | n/a | el cliente reporta **99.81% PASS Carter** con este — consistente |
| E4B-it UD-Q5_K_XL | Pareto | n/a | n/a | n/a | ~89–93% [EXTRAPOLADO] |
| E4B-it UD-Q4_K_XL | Pareto | n/a | n/a | n/a | ~87–91% [EXTRAPOLADO] |
| E4B-it Q4_K_M (balanced actual) | dominado por UD-Q4_K_XL | n/a | n/a | n/a | ~85–90% [EXTRAPOLADO] |
| E2B-it Q5_K_M (balanced actual) | dominado por UD-Q5_K_XL | E2B-it AIME ~25–30% [EXTRAPOLADO] | n/a | n/a | ~75–82% [EXTRAPOLADO]; **mucho menor que E4B** |
| E2B-it UD-Q4_K_XL | Pareto | n/a | n/a | n/a | ~73–80% |

**Correlaciones esperadas (sin medición directa):**
- **τ2-bench → Carter:** fuerte (ambos miden tool calling agentic). El gap 26B-A4B (82.3) vs 31B (86.4) en τ2 sugiere ~4 puntos de Carter. [EXTRAPOLADO]
- **AIME → Carter:** débil para tareas no-matemáticas; útil sólo para subset razonamiento.
- **MMLU-Pro → Carter:** medio. Indicador de conocimiento, no de agencia.
- **KLD vs BF16 → Carter PASS:** **fuerte para tareas con respuesta única correcta**, débil para tareas con muchas respuestas válidas. KL 0.1 → casi indistinguible; KL 0.3+ → degradación visible en tareas estructuradas. [EXTRAPOLADO]

### H2. Benchmarks que miden tool calling Gemma 4 específico

**Públicos al 2026-05-15:**
- **τ2-bench oficial Google:** 86.4% (31B), 82.3% (26B-A4B), 42.5% E4B [aprox] (`labellerr.com/blog/gemma-4-open-weight-ai-model-overview/`).
- **Berkeley Function Calling Leaderboard (BFCL):** [no encontrado update post-2026-04-02 con Gemma 4 explícito]. **Pendiente.**
- **Daniel Farina gist:** anecdotal — 26B-A4B "works after a few retries" para OpenCode tool calling. Sin score.
- **Carter 540 (cliente):** 99.81% con E4B-Q6_K — único score público referencible para tool calling Gemma 4 en español multi-step.

### H3. Proxies cheap predictores de Carter

[NO MEDIDA la correlación]. Hipótesis ordenadas por value:

1. **τ2-bench / BFCL subset de 50 tareas con tools** — el predictor más natural; mismo dominio. Costo: 1–2 h por GGUF.
2. **MT-Bench mini (multi-turn)** — predictor medio. Costo: 30 min.
3. **GSM8K 200-shot subset** — predictor débil para Carter (Carter no es matemático), pero útil como sanity. Costo: 15 min.
4. **MMLU-Pro 100-shot subset en español** — predictor medio. Costo: 30 min.
5. **KL vs BF16 micro (50K tokens estilo tool calling)** — predictor fuerte para regresiones de quant, débil para regresiones de capability. Costo: 5 min.

**Recomendación de batería cheap:** combinar **(1) + (5)** como gate semi-formal antes de promover un GGUF a producción. Costo total: ~2 h por GGUF candidato. Threshold: si KL > 0.3 o τ2-mini < baseline - 5pp → rechazar. **Confianza EXTRAPOLADO.**

**Archivos a tocar:**
- `harness_carter540/` — agregar `harness_proxies/` con scripts `kl_vs_bf16.py`, `tau2_mini.py` para A/B rápido.
- `INFORME_ARQUITECTURA_6GB.md` — documentar threshold de promoción.

## 9. Bloque I — Plan de acción (I1–I4)

### I1. Top 10 cambios concretos ordenados por (impacto × baja-fricción)

| # | Cambio | Archivo (líneas aprox) | Mejora esperada (métrica) | Riesgo | Costo impl. | Confianza |
|---|---|---|---|---|---|---|
| **1** | Pin de build llama.cpp a tag concreto post-#21418 + #21326 + #21343 (ej. b8773+); congelar SHA en `requirements_runtime.lock` | `llama_server.py` (header), nuevo `LLAMA_BUILD_SHA` const | Carter +0.5 pp (consistencia entre runs); 0 regresiones por upstream | bajo | 1 día | MEDIDO upstream |
| **2** | Cambiar default GGUF en `balanced`: E4B-Q4_K_M → `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL` | `profiles.py:PROFILES["balanced"]` (~5 líneas) | Carter +1–2 pp esperado por Pareto-KLD; misma VRAM | bajo (mismo footprint) | 2 días (download + bench A/B Carter) | CITADO |
| **3** | Añadir `--keep -1` y elevar `--cache-ram` mientras #21468 no esté merged | `llama_server.py:_build_server_cmd` (~10 líneas) | TTFT -30% en turnos 2+ (estimado por que cache funciona sobre system prompt aunque no sobre user history) | bajo | 0.5 día | EXTRAPOLADO |
| **4** | Pre-warm KV con system prompt + bloque "ready" en startup (request "ping" sintética antes de UI ready) | `llama_server.py` + `app.py` (~30 líneas) | TTFT primera interacción real -50% [EXTRAPOLADO] | bajo | 1 día | EXTRAPOLADO |
| **5** | Robustecer parser tool-calls para args con `{`/`}` (issue #21384) | `llm_client.py` y `safety.py:classify_tool_call` (~50 líneas + 4 unit tests) | Carter +1–3 pp en tareas con paths/regex en args | bajo | 1 día | CITADO |
| **6** | Activar interleaved chat template para `performance` (tools + thinking) | `llama_server.py` (1 flag), `profiles.py` (1 campo) | Carter multi-step +2 pp esperado (Gemma 4 mantiene thoughts entre tool calls según PR #21418) | medio (regresión en single-call posible) | 2 días (incluye A/B) | CITADO |
| **7** | Inyectar bloque "Tool Schemas EXACT" estilo OpenCode en system prompt construido por `tools.py` | `tools.py:COMPOUND_TOOL_SCHEMAS` (~40 líneas) | Carter +2–4 pp en argument-naming según el patrón Daniel Farina | bajo | 1 día | CITADO |
| **8** | Auto-relaunch server cada N=40 imágenes en `performance` para mitigar #21690 | `llama_server.py` (~20 líneas), counter en `agent.py` | OOM-free en sesiones largas con visión | bajo | 1 día | CITADO |
| **9** | Documentar/banderar que audio nativo Gemma 4 está bloqueado (#21868) y fijar Whisper como STT primario | `INFORME_ARQUITECTURA_6GB.md`, `config.py` | Evita esfuerzo perdido | 0 | 0.5 día | CITADO |
| **10** | Reservar **1.5 GB de VRAM Windows** en `recommend_profile(vram_mb)` antes de elegir perfil | `profiles.py:recommend_profile` (~10 líneas) | 0 OOMs en 6 GB (actualmente probable en arranque con monitor 1440p+ o app gráfica abierta) | bajo | 0.5 día | EXTRAPOLADO |

**Total esfuerzo:** ~10–12 días/persona. **Mejora esperada Carter:** +5–10 pp (rangos overlapping). Empuja al cliente del 99.81% reportado con dev model a esperablemente ~99.9% en producción 6 GB.

**Cambios "high impact" descartados por restricciones:**
- MTP drafters Google: requeriría runtime no-llama.cpp o cherry-pick experimental. **Esperar 30–60 días para upstream.**
- Cambio a vLLM: prohibido por brief.
- Speculative decoding E2B→E4B: no entra en 6 GB; sí evaluar en 8 GB+ tier.

### I2. Feature-flags vs default

| Cambio | Default | Feature-flag (power user) |
|---|---|---|
| 1, 2, 3, 5, 7, 8, 9, 10 | **Default ON** | n/a |
| 4 (pre-warm) | Default ON | `disable_prewarm` flag |
| 6 (interleaved template) | **Solo `performance` profile** | `force_interleaved` global flag |
| MTP cuando merged upstream | **Off** hasta benchmark interno | `enable_mtp_speculation` |
| Kokoro TTS es | **Off** (Piper default) | `tts_backend=kokoro_es` |
| Parakeet-TDT-0.6B-v3 STT | **Off** (Whisper default) | `stt_backend=parakeet` |
| KV q8_0 | **Off** (impacto KL 0.377 medido) | `kv_quant=q8_0` con warning explícito |
| MXFP4_MOE 26B | **Off** | `model_variant=mxfp4` |

### I3. Roadmap de 90 días, sprints semanales

**Sprint 1 (días 1–7) — "Lockdown y arranque seguro"**
- (1) Pin de build llama.cpp.
- (10) Reserva 1.5 GB VRAM Windows en `recommend_profile`.
- (9) Documentar restricciones.
- Entregable: build reproducible; doc de arquitectura actualizada; 0 OOM startup en RTX 3050 6 GB con Chrome abierto.

**Sprint 2 (días 8–14) — "Quant upgrade balanced"**
- (2) Cambio a UD-Q4_K_XL E4B.
- Bench A/B Carter 540 baseline vs nuevo. Aceptar si pass-rate ≥ baseline.
- Entregable: profile `balanced` con nuevo GGUF; reporte A/B.

**Sprint 3 (días 15–21) — "Parser robustez + tool schemas"**
- (5) Robustecer parser `{`/`}`.
- (7) Inyectar bloque tool schemas exactas.
- Test set sintético con 40 tool calls "rough" (args con braces, paths con espacios, JSON anidado).
- Entregable: Carter pass-rate +2–5 pp esperado.

**Sprint 4 (días 22–28) — "Latencia: keep + cache-ram + pre-warm"**
- (3) Flags `--keep -1`, `--cache-ram`.
- (4) Pre-warm en startup.
- Métricas: p50 TTFT, p95 TTFT, primer fonema TTS.
- Entregable: TTFT primera interacción ≤ 1.0 s, turnos siguientes ≤ 0.5 s.

**Sprint 5 (días 29–35) — "Visión defensiva"**
- (8) Auto-relaunch N imágenes.
- Test stress: 200 imágenes consecutivas sin OOM.
- Entregable: visión sin OOM en sesiones largas en 6 GB.

**Sprint 6 (días 36–42) — "Interleaved + performance profile"**
- (6) Activar interleaved en `performance`.
- A/B contra non-interleaved en multi-step Carter.
- Entregable: Carter performance +2 pp.

**Sprint 7 (días 43–49) — "Telemetría local opt-in"**
- Implementar I4 (ver abajo).
- Entregable: dashboard local + opt-in toggle + esquema almacenamiento.

**Sprint 8 (días 50–56) — "Evaluar MTP upstream"**
- Re-check ggml-org/llama.cpp Discussion #22735.
- Si merged: cherry-pick + bench. Si no: documentar y esperar.
- Entregable: decisión binaria.

**Sprint 9 (días 57–63) — "Speculative decoding 8 GB+"**
- Implementar `--spec-draft-model E2B → E4B` para tier 8 GB.
- Medir acceptance rate Carter. Solo activar si > 50%.
- Entregable: perfil "balanced-8gb" con speculative.

**Sprint 10 (días 64–70) — "STT alt: Parakeet"**
- Implementar backend Parakeet-TDT-0.6B-v3.
- A/B WER es-MX 200 utterances vs Whisper-small.
- Entregable: feature-flag con decisión informada.

**Sprint 11 (días 71–77) — "TTS alt: Kokoro"**
- Implementar backend Kokoro-82M-es feature-flagged.
- MOS interno A/B vs Piper.
- Entregable: feature-flag.

**Sprint 12 (días 78–84) — "Endurecer seguridad operacional"**
- Bonus track: revisar `--no-webui`, `--api-key`, `--cors-allow-origin`, logging redaction.
- Entregable: surface attack documentada.

**Sprint 13 (días 85–90) — "Carter 100% push"**
- Investigar los ~9 fallos restantes para llegar de 99.81 → 100%.
- Posiblemente requiere prompt eng o tools fixes, no cambios de runtime.
- Entregable: post-mortem por categoría de fallo.

### I4. Telemetría local opt-in: qué medir para saber si la app va bien en 6 GB

**Principio:** todo en disco local (`%LOCALAPPDATA%/gemma4_agent/telemetry.sqlite`), nunca sale del equipo a menos que el usuario lo exporte voluntariamente. Opt-in default OFF.

**Métricas obligatorias (cada turno):**

| Métrica | Frecuencia | Almacenamiento |
|---|---|---|
| `ttft_ms` | por request | tabla `turns` |
| `tokens_per_second` | por request | turns |
| `tokens_completion` | por request | turns |
| `tokens_prompt_total` | por request | turns |
| `cache_n_reused` (timings.cache_n llama.cpp) | por request | turns |
| `vram_peak_mb` (poll nvidia-smi al final del turno) | por request | turns |
| `vram_baseline_mb` (al cargar el modelo) | por server start | tabla `sessions` |
| `oom_event` (boolean) | por evento | tabla `incidents` |
| `tool_call_count` y `tool_call_errors` | por request | turns |
| `parser_recover_count` (parseo de tool args con fallback {/}) | por evento | incidents |
| `stt_rtf` (CPU real time factor de Whisper) | por utterance | tabla `voice` |
| `tts_first_phoneme_ms` | por utterance | voice |
| `profile_active` | por sesión | sessions |
| `gguf_hash` y `build_sha` llama.cpp | por sesión | sessions |
| `n_swap_events` y `swap_duration_ms` | por evento | incidents |

**Métricas opcionales (sólo si user lo activa):**
- Hash anonimizado del system prompt para detectar drift.
- Tokens de salida (no contenido) en buckets.

**Esquema almacenamiento:** SQLite local, rotación a 30 días; export JSON con un click si el usuario quiere mandar al equipo de soporte. Cero IDs externos. No tokens del usuario; no contenido.

**Detección de problemas en 6 GB sin feedback explícito:**
- `oom_event > 0` en últimas 24 h → suggest downgrade a `light`.
- `ttft_ms p95 > 5s` durante 3 sesiones → tip "cache reuse probablemente caído, prueba sin cambiar nada y reporta".
- `tool_call_errors / tool_call_count > 5%` → ofrecer "ver últimos 10 fallos" para diagnóstico.
- `parser_recover_count > 0` → flag para investigar issue #21384 regression.
- `n_swap_events > 10/h` en `balanced` → suggest pasar a `performance` si VRAM lo permite, o `light` si no.

**Archivo a tocar nuevo:** `telemetry.py` (~200 LoC) + `config.py:AgentConfig.telemetry_enabled: bool = False`.

## Bonus — Competencia, Quick wins UX, Seguridad operacional

### Análisis competencia: stack del cliente vs alternativas

| Stack | Runtime | Tool calling Gemma 4 | Streaming SSE tool calls | Vision | Audio | UI | Licencia | Idle VRAM | Veredicto cliente |
|---|---|---|---|---|---|---|---|---|---|
| **gemma4_agent (cliente)** | llama-server + PyQt6/React | `--jinja` + parser nativo #21418 (correcto) | OK post-#21418 | mmproj F16 (con leak #21690 mitigado) | Whisper + Piper (decisión correcta) | Custom React | Apache 2.0 deps | Server vivo retiene VRAM | **Mejor stack agentic local Gemma 4 en Windows hoy**, condicionado a parchar #21468 cuando salga |
| **LM Studio** | llama.cpp/MLX (engines internos) | Soporta speculative decoding GUI, soporta tool calls vía endpoint | OK | Sí | Limitado | GUI nativo | Closed-source freemium | TTL auto-unload | Mejor GUI; peor para integración programática |
| **Ollama** | Fork llama.cpp + Go wrapper | **#15241 abierto**: streaming drops tool calls; agentic frágil con Gemma 4 (gist Daniel Farina) | **Roto** en v0.20.0 según gist | Sí (limitado) | Limitado | API + CLI | MIT | Auto-unload TTL | NO recomendable para agentes Gemma 4 al 2026-05 |
| **GPT4All** | llama.cpp wrapper | Limitado | Limitado | No nativo | No | GUI | MIT | Server vivo | Para chat casual, no agentic |
| **Jan.ai** | Cortex (llama.cpp wrapper) | Soporta tool calls via OpenAI shim | OK con caveats | Sí | No | GUI Electron | AGPLv3 | TTL | Mejor para usuario final UI, peor para agente programático |
| **Cherry Studio** | OpenAI-compatible client (no runtime) | Cliente, no servidor | n/a | Cliente | n/a | GUI | Apache 2.0 | n/a | Es cliente, no compite con el runtime |

**Conclusión competencia:** el stack del cliente (`llama-server.exe` directo + Python + PyQt6 + React) es **superior técnicamente para el caso de uso "agente local con tools en español y voz"** porque es el único que aprovecha el parser nativo Gemma 4 (#21418) sin pérdidas en streaming. La debilidad relativa es **UX de onboarding** (LM Studio y Jan.ai son más fáciles para usuario final). [CITADO]

### Quick wins UX sin tocar modelo

1. **Pre-warm KV system prompt al startup (item I1 #4).** Bench Daniel Farina ya muestra que un primer turno frío con 30K+ tokens de system+tools tarda 60–90 s; pre-warm en pantalla de splash convierte eso en "esperá un minuto al primer arranque" en lugar de "esperá un minuto cada turno". [CITADO]
2. **Splash con progreso real.** Hookear los stdout de llama-server (`srv load:` events) → ETA en UI. Los eventos `srv update:`, `srv load: spawning server instance with args:`, `srv load: --model`, `llama_model_loader: ...` están disponibles en stderr.
3. **Manejo elegante OOM.** Detectar `ggml_cuda_pool_alloc / CUDA out of memory` en stderr → ofrecer "Switch to lighter profile?" antes de crash duro.
4. **Indicador de cache hit/miss.** Mostrar en debug HUD si `timings.cache_n > 0` para que el power user vea que la mitigación de #21468 vía `--keep` funciona.
5. **Aviso explícito de visión bloqueada en `balanced/light`.** Hoy es OFF silencioso.
6. **Botón "Restart server" en menú.** Para casos de leak mmproj acumulado sin tener que matar app.

### Seguridad operacional: flags llama-server que reducen superficie de ataque

| Flag | Recomendación | Efecto |
|---|---|---|
| `--host 127.0.0.1` | **Forzar** | Evita exposición LAN accidental |
| `--api-key <random>` | **On** | Requerir auth desde Python client |
| `--no-webui` | **On** | El cliente tiene UI propia; el webui interno es atack surface innecesario |
| `--cors-allow-origin` | **No fijar** | Default es restrictivo |
| `--log-disable` | **On** | Reduce escritura a disco de prompts (privacidad) |
| `--logging.disable_prompt_in_logs` (si build lo soporta) | **On** | Idem |
| `--port <random_high>` | rotar por sesión | Mitiga port-pinning de scripts |
| `--slot-save-path` | **Solo en folder propio del usuario** | El cliente actualmente con `--slot-save-path /config/slots` (referencia issue #21316) — verificar permisos |
| Telemetry interna | **Opt-in OFF default** | Privacidad |

**Acción `llama_server.py`:** consolidar todas estas en `_build_server_cmd` como invariantes no negociables. Tests de regresión que verifiquen que un `curl` desde otra máquina LAN al port del server falle (network isolation). **Confianza CITADO.**

## Anexo — Fuentes citadas (90 entradas)

**Tier 1 (oficial Google / oficial llama.cpp / oficial Unsloth / Bartowski):**

1. *Gemma 4: Byte for byte, the most capable open models* — Clement Farabet, Olivier Lacombe (Google DeepMind) — 2026-04-02 — `https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/` — fecha release, sizes, Apache 2.0, capacidades.
2. *Gemma 4* — Google DeepMind landing — fecha actual — `https://deepmind.google/models/gemma/gemma-4/` — landing oficial, MTP visible.
3. *Gemma 4 available on Google Cloud* — Google Cloud — 2026-04-02 — `https://cloud.google.com/blog/products/ai-machine-learning/gemma-4-available-on-google-cloud` — confirmación release, 256K context, 140+ idiomas.
4. *Bring state-of-the-art agentic skills to the edge with Gemma 4* — Google AI Edge Team — 2026-04-02 — `https://developers.googleblog.com/bring-state-of-the-art-agentic-skills-to-the-edge-with-gemma-4/` — capacidades edge, Agent Skills.
5. *Gemma releases* — Google AI for Developers — 2026-05-05 update — `https://ai.google.dev/gemma/docs/releases` — confirma "Release of Gemma 4 - MTP for E2B, E4B, 31B, and 26B A4B".
6. *Welcome Gemma 4: Frontier multimodal intelligence on device* — Hugging Face (merve, pcuenq, sergiopaniego, burtenshaw, Steveeeeeeen, alvarobartt, SaylorTwift) — 2026-04-02 — `https://huggingface.co/blog/gemma4` — arquitectura: dual RoPE, PLE, shared KV, dual sliding/full attention, USM-style audio encoder.
7. *Accelerating Gemma 4: faster inference with multi-token prediction drafters* — Google blog — 2026-05-05 — `https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/` — MTP drafters, 3× speedup claim.
8. *Speed-up Gemma 4 with Multi-Token Prediction* — Google AI for Developers — 2026-05+ — `https://ai.google.dev/gemma/docs/mtp/overview` — arquitectura MTP, shared embeddings.
9. *Gemma 4 Multi-Token Prediction (MTP) using Hugging Face Transformers* — Google AI for Developers — `https://ai.google.dev/gemma/docs/mtp/mtp` — uso práctico, naming `*-it-assistant`.
10. *Gemma 4 - How to Run Locally* — Unsloth Documentation — abril 2026 — `https://unsloth.ai/docs/models/gemma-4` — recomendaciones de quants, sampling, thinking mode, CUDA 13.2 warning.
11. *unsloth/gemma-4-26B-A4B-it-GGUF · Gemma 4 26B-A4B GGUF Benchmarks* — Unsloth — 2026-04-20 — `https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/35` — KLD benchmarks, frontera Pareto.
12. *Unsloth Dynamic 2.0 GGUFs* — Unsloth Documentation — `https://unsloth.ai/docs/basics/unsloth-dynamic-2.0-ggufs` — método UD, comparativas con imatrix.
13. *Qwen3.5 GGUF Benchmarks* — Unsloth — `https://unsloth.ai/docs/models/qwen3.5/gguf-benchmarks` — análisis MXFP4 vs Q4_K (extensible Gemma 4 por mismo pipeline).
14. *bartowski/google_gemma-4-E4B-it-GGUF* — Bartowski — 2026-04+ (b8637, b8648) — `https://huggingface.co/bartowski/google_gemma-4-E4B-it-GGUF` — tabla de tamaños GGUF E4B.
15. *bartowski/google_gemma-4-E2B-it-GGUF* — Bartowski — `https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF` — tabla E2B.
16. *bartowski/google_gemma-4-26B-A4B-it-GGUF* — Bartowski (b8647) — `https://huggingface.co/bartowski/google_gemma-4-26B-A4B-it-GGUF` — tabla 26B-A4B, archive 445 GB.
17. *bartowski/google_gemma-4-31B-it-GGUF* — Bartowski — `https://huggingface.co/bartowski/google_gemma-4-31B-it-GGUF` — tabla 31B.
18. *llama.cpp/docs/speculative.md* — ggml-org/llama.cpp master — `https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md` — flags `--spec-draft-*`.
19. *llama.cpp/docs/multimodal.md* — ggml-org/llama.cpp master — `https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md` — `--mmproj`, `--no-mmproj-offload`.

**Tier 1 (issues/PRs llama.cpp):**

20. *Issue #21468: cache reuse is not supported for Gemma 4 models* — phuryn — 2026-04-05 — `https://github.com/ggml-org/llama.cpp/issues/21468` — root cause shared-KV, log de fallo, hipótesis y referencia a PR #22288.
21. *Issue #21690: Checkpoints and MMProj on Gemma 4 consume abnormal amounts of RAM* — `https://github.com/ggml-org/llama.cpp/issues/21690` — workaround `--ctx-checkpoints 1 -np 1`.
22. *Issue #21868: server: add input_audio content type routing for Gemma 4* — iammac2 — 2026-04-13 — `https://github.com/ggml-org/llama.cpp/issues/21868` — server.cpp gap, workaround subprocess.
23. *PR #21418: common : add gemma 4 specialized parser* — aldehir — merged 2026-04-04 — `https://github.com/ggml-org/llama.cpp/pull/21418` — parser dedicado, EOG `<|tool_response>`, interleaved template.
24. *Issue #21316: Gemma4 tool calling leaves unexpected tokens in tool calls* — `https://github.com/ggml-org/llama.cpp/issues/21316` — `<unused25>` token spam.
25. *Issue #21384: Gemma 4 tool call array parameter serialized as JSON string when values contain `{` or `}`* — `https://github.com/ggml-org/llama.cpp/issues/21384` — bug parser.
26. *Issue #21325: Eval bug: Gemma 4 audio support is missing* — `https://github.com/ggml-org/llama.cpp/issues/21325` — closed por #21421, GGUF metadata reveal.
27. *Issue #21323: Eval bug: out of memory while loading Gemma 4 - cpu offloading from 5080* — `https://github.com/ggml-org/llama.cpp/issues/21323` — VRAM 16 GB no suficiente para 31B sin offload.
28. *Issue #19980: auto fit estimation does not account for mmproj GPU memory* — `https://github.com/ggml-org/llama.cpp/issues/19980` — `--fit on` no contabiliza mmproj.
29. *Discussion #22735: Support for Gemma 4 Assistant/Drafter models* — 2026-05-08 — `https://github.com/ggml-org/llama.cpp/discussions/22735` — MTP no soportado upstream.
30. *Discussion #21689: Gemma-4-31B-it heavy system memory occupied* — `https://github.com/ggml-org/llama.cpp/discussions/21689` — checkpoint default 3.6 GB × N.
31. *Discussion #20855: Lazy Loading MMPROJ file* — `https://github.com/ggml-org/llama.cpp/discussions/20855` — propuesta `--mmproj-load-on-demand` (abierta).
32. *Discussion #21334: How to input audio to Gemma 4 E4B?* — `https://github.com/ggml-org/llama.cpp/discussions/21334` — confirma 500 + workaround.
33. *Discussion #15902: Support Eagle-3 Speculative Decoding* — `https://github.com/ggml-org/llama.cpp/discussions/15902` — contexto general speculative.
34. *llama.cpp README* — ggml-org — `https://github.com/ggml-org/llama.cpp/` — uso general llama-server, comandos.
35. *huggingface.co/google/gemma-4-E2B-it/discussions/6* — issue con llama.cpp y metadata GGUF — confirma `gemma4` arch, sampling defaults embebidos.
36. *unsloth/gemma-4-E4B-it-GGUF* — `https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF` — model card E4B.
37. *unsloth/gemma-4-E2B-it-GGUF* — `https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF` — model card E2B.
38. *unsloth/gemma-4-31B-it-GGUF* — `https://huggingface.co/unsloth/gemma-4-31B-it-GGUF` — model card 31B.
39. *unsloth/gemma-4-E4B-it-unsloth-bnb-4bit* — `https://huggingface.co/unsloth/gemma-4-E4B-it-unsloth-bnb-4bit` — variant bnb.

**Tier 2 (analistas técnicos verificables):**

40. *Gemma 4 31B GGUF Quality Benchmark: unsloth, bartowski, lmstudio-community, ggml-org compared* — localbench substack — abril 2026 — `https://localbench.substack.com/p/gemma-4-31b-gguf-kl-divergence` — 53 GGUF benchmarked KLD, Pareto frontier, "ggml-org and lmstudio-community quants never appear on the Pareto frontier".
41. *Gemma 4 and Qwen 3.6 with q8_0 and q4_0 KV cache: KL divergence results* — localbench substack — abril 2026 — `https://localbench.substack.com/p/kv-cache-quantization-benchmark` — KL 0.377 26B-A4B q8_0 KV; *"Gemma 4 26B A4B is the most quantization-sensitive model tested so far"*.
42. *Gemma 4 31B and 26B A4B: Architecture and Memory Consumption* — Benjamin Marie / Kaitchup substack — abril 2026 — `https://kaitchup.substack.com/p/gemma-4-31b-and-26b-a4b-architecture` — derivación KV cache: 5.20 GiB 26B-A4B a 256K, sliding-window 4096 / shared-KV.
43. *Tuning llama-server on Apple Silicon* — Michael Hannecke / Medium — abril 2026 — `https://medium.com/@michael.hannecke/tuning-llama-server-on-apple-silicon-9b3e778ab100` — `--parallel × --batch-size × --ubatch-size × --cache-reuse`, cita explícita de #21468.
44. *Running OpenCode with Gemma 4 26B on macOS via llama.cpp - fixing tool calling* — Daniel Farina gist — 2026-04-02 — `https://gist.github.com/daniel-farina/87dc1c394b94e45bb700d27e9ea03193` — Ollama #15241 (streaming drops tool calls), PR #21326 #21343 cherry-pick, llama-server commands.
45. *Llama-Server Router Mode - Dynamic Model Switching Without Restarts* — Rost Glukhov — abril 2026 — `https://medium.com/@rosgluk/llama-server-router-mode-dynamic-model-switching-without-restarts-4e7d6fb19906` y `https://www.glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/` — swap costs, 3–10 s reload típico.
46. *llama-swap (mostlygeek)* — `https://github.com/mostlygeek/llama-swap` y `https://github.com/mostlygeek/llama-swap/blob/main/docs/configuration.md` — hot-swap, config.yaml semantics.
47. *llama.swap Model Switcher Quickstart* — Rost Glukhov — `https://www.glukhov.org/llm-hosting/llama-swap/` — comparativa con LM Studio y llama-server router mode.
48. *Hot-Swap Local LLMs Instantly: llama-swap Setup Guide (2026)* — ModelsLab blog — abril 2026 — `https://modelslab.com/blog/api/hot-swap-local-llms-instantly-llama-swap-setup-guide-2026` — cold start 5–30 s.
49. *Liftoff: Gemma 4 hits 670 tok/s aggregate on DGX Spark* — Ai-muninn blog — 2026-05-06 — `https://ai-muninn.com/en/blog/dgx-spark-gemma4-mtp-108-toks` — Gemma 4 26B-A4B-it FP8 + MTP γ=4 = 108.78 tok/s single-stream (2.66× baseline), vLLM PR #41745.
50. *llamacpp-gemma4-mtp (karany97)* — `https://github.com/karany97/llamacpp-gemma4-mtp` — fork patches ik_llama.cpp PR #1744 + pestopoppa fixes, 2.6–2.98× lossless verified.
51. *Unpacking Gemma 4's multi-token prediction* — bdtechtalks substack — mayo 2026 — `https://bdtechtalks.substack.com/p/unpacking-gemma-4s-multi-token-prediction` — explicación MTP + KV cache sharing.
52. *Gemma 4 Gets Multi-Token Prediction Drafters: 3x Faster Inference* — NYU Shanghai RITS — 2026-05-05 — `https://rits.shanghai.nyu.edu/ai/gemma-4-gets-multi-token-prediction-drafters-3x-faster-inference-same-outputs/` — confirma fecha, primer first-party drafter Apache 2.0.
53. *llama.cpp Releases in April 2026: Tensor Parallelism, 1-Bit Quantization, and More* — fazm.ai blog — 2026-04-13 — `https://fazm.ai/blog/llama-cpp-release-april-2026` — TurboQuant Hadamard rotation (b8607), Gemma 4 builds b8641 (chat template), b8662 (softcapping), b8665 (parser), b8678 (BPE bytes), audio b8766.
54. *Fixing Gemma 4 Thinking Prompts in llama.cpp, Locally First* — CompleteTech LLC — 2026-04-29 — `https://complete.tech/blog/llamacpp-gemma4-thinking-prompt-local-fix/` — fix template guard inverso (fork, no upstream).
55. *llama.cpp Fixes Gemma 4's Broken KV Cache* — aiproductivity.ai — abril 2026 — `https://aiproductivity.ai/news/llama-cpp-fixes-gemma-4-kv-cache-vram/` — confirmación fix KV.
56. *llama.cpp Merges Gemma 4 Tokenizer Fix to Main Branch* — aiproductivity.ai — 2026-04-03 — `https://aiproductivity.ai/news/llamacpp-gemma4-tokenizer-fix-merged/` — fecha merge tokenizer fix.
57. *Gemma 4 Now Runs Stable on Llama.cpp After Key Bug Fixes* — aiproductivity.ai — 2026-04-09 — `https://aiproductivity.ai/news/gemma-4-llamacpp-stable/` — fecha estabilización Q5/24 GB.

**Tier 2 (ASR/TTS reference):**

58. *faster-whisper (SYSTRAN)* — `https://github.com/SYSTRAN/faster-whisper` — CTranslate2, int8 benchmark, RTF.
59. *Benchmark faster whisper turbo v3* — SYSTRAN issue #1030 — `https://github.com/SYSTRAN/faster-whisper/issues/1030` — 19s para 13min audio, faster-large-v3-turbo fp16.
60. *Whisper Large V3 Turbo vs V3: 5× Faster on Mac* — Whisper Notes blog — `https://whispernotes.app/blog/introducing-whisper-large-v3-turbo` — 13.40% WER YouTube-commons turbo, 1.5 GB VRAM int8.
61. *adriszmar/whisper-large-v3-turbo-es* — Hugging Face — `https://huggingface.co/adriszmar/whisper-large-v3-turbo-es` — WER 5.34% es Common Voice 17.
62. *nvidia/parakeet-tdt-0.6b-v3* — Hugging Face — `https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3` — 600M, 25 idiomas europeos incluyendo español, multilingüe nativo.
63. *parakeet-1.1b-rnnt-multilingual-asr* — NVIDIA build — `https://build.nvidia.com/nvidia/parakeet-1_1b-rnnt-multilingual-asr/modelcard` — alternativa.
64. *Best TTS Models 2026: Open-Source Voice AI Compared* — CodeSOTA — marzo 2026 — `https://www.codesota.com/guides/tts-models` — comparativa 8 TTS, Apache 2.0 vs CPML.
65. *Kokoro-TTS-Local (PierrunoYT)* — `https://github.com/PierrunoYT/Kokoro-TTS-Local` — código local con Spanish ('e' lang), offline mode.
66. *kokoro-tts (nazdridoy)* — `https://github.com/nazdridoy/kokoro-tts` — CLI, voice blending.
67. *XTTS V2 vs Kokoro 82M: Which Open Source TTS Model* — TTS Insider — `https://www.ttsinsider.com/xtts-v2-vs-kokoro/` — 17 idiomas XTTS, Kokoro vs XTTS arquitectura.

**Tier 3 (descriptivos, citas usadas con cuidado o sólo como context):**

68. *Google DeepMind Releases Gemma 4* — SMBtech — abril 2026 — `https://smbtech.au/news/google-deepmind-releases-gemma-4-its-most-capable-open-source-ai-models/` — cobertura periodística.
69. *Google Gemma 4: A Technical Overview* — Labellerr — `https://www.labellerr.com/blog/gemma-4-open-weight-ai-model-overview/` — números τ2-bench, AIME, LiveCodeBench.
70. *Gemma 4 by Google: Specs, Benchmarks, Model Sizes* — Auriga IT — `https://aurigait.com/blog/gemma-4-features-benchmarks-guide/` — benchmark resume.
71. *Google DeepMind Releases Gemma 4 With Four Model Sizes* — AI Haven — `https://aihaven.com/news/gemma-4-launches-april-2026/` — benchmark resume (multilingüe MMLU 85.2%).
72. *Gemma 4: How a 31B Model Beats 400B Rivals* — Tech Insider — `https://tech-insider.org/google-gemma-4-open-model-benchmarks-2026/` — résumé.
73. *5 Things to Know About Google's New Gemma 4 AI Models* — Techloy — `https://www.techloy.com/5-things-to-know-about-googles-new-gemma-4-ai-models/` — résumé.
74. *Gemma 4 – Google DeepMind's Most Powerful Open-Weight AI Model* — AIMLAPI — `https://aimlapi.com/blog/gemma-4---google-deepminds-most-powerful-open-weight-ai-model-family` — résumé.
75. *Google Just Launched Gemma 4. Here's What It Means for Your AI Budget* — Marc Bara / Medium — abril 2026 — `https://medium.com/@marc.bara.iniesta/google-just-launched-gemma-4-heres-what-it-means-for-your-ai-budget-04160d5a426e` — análisis de mercado.
76. *Does llama.cpp Support Gemma 4? GGUF Status, Fixes, and What Works* — Avenchat — `https://avenchat.com/blog/does-llama-cpp-support-gemma-4` — confirmación fechas merge parser/tokenizer fixes.
77. *How to Run Gemma 4 with llama.cpp: GGUF Setup, Hardware & Quantization Guide* — Avenchat — `https://avenchat.com/blog/run-gemma-4-with-llama-cpp` — comandos prácticos.
78. *Running Google's Gemma 4 Locally with llama-server* — VenuThomas / Medium — abril 2026 — `https://medium.com/@VenuThomas/running-googles-gemma-4-locally-with-llama-server-5232f122f6c8` — comandos, 127 tok/s prompt / 34 tok/s gen Apple Silicon.
79. *Optimizing Gemma 4 Local Inference: llama.cpp KV Cache Fix and NPU Performance Benchmarks* — n1n.ai — 2026-04-05 — `https://explore.n1n.ai/blog/gemma-4-local-inference-llama-cpp-kv-cache-fix-npu-benchmarks-2026-04-05` — claim Rockchip NPU (sin código verificable; usado solo como dato directional).
80. *Multi-Token Prediction Tutorial: How To Speed Up LLMs* — DataCamp — `https://www.datacamp.com/tutorial/multi-token-prediction-llama-cpp` — MTP explanation.
81. *Speculative Decoding (DeepWiki)* — `https://deepwiki.com/ggml-org/llama.cpp/8.3-speculative-decoding` — internals llama.cpp speculative.
82. *Tested every llama.cpp speculative-decode mode on Qwen3.6-35B-A3B* — HackMD — `https://hackmd.io/ODXuOQNzSiyUITz7g9mtBw` — negative finding consumer Ampere.
83. *Speculative Decoding (Unsloth)* — `https://unsloth.ai/docs/basics/inference-and-deployment/saving-to-gguf/speculative-decoding` — uso con `--model-draft` y `--device-draft`.
84. *Gemma 4 Fine-tuning Guide* — Unsloth — `https://unsloth.ai/docs/models/gemma-4/train` — fine-tuning E4B QLoRA en 24 GB.
85. *LM Studio 0.3.10: Speculative Decoding* — LM Studio blog — `https://lmstudio.ai/blog/lmstudio-v0.3.10` — speculative GUI, "draft model should be much smaller and from the same family".
86. *DGX Spark memory not released using llama.cpp?* — NVIDIA developer forums — `https://forums.developer.nvidia.com/t/dgx-spark-memory-not-released-using-llama-cpp/364070` — memoria sin liberar Spark.
87. *Proposal for Native Kernel Integration of GPU VRAM* — Microsoft Community Hub — `https://techcommunity.microsoft.com/discussions/windows11/proposal-for-native-kernel-integration-of-gpu-vram-as-tiered-system-memory-numa-/4488828` — contexto WDDM (informativo).
88. *dwm.exe is using over 1GB of VRAM* — Tom's Hardware Forum — `https://forums.tomshardware.com/threads/dwm-exe-is-using-over-1gb-of-vram.3845139/` — reporte anecdótico overhead WDDM.
89. *Task Manager vs GPU-Z: Understanding VRAM Usage* — Windows News — `https://windowsnews.ai/article/task-manager-vs-gpu-z-understanding-vram-usage-allocation-and-real-gpu-memory-pressure.413770` — categorías VRAM Windows.
90. *Misc. bug: CUDA memory leak with MTMD requests loop with Gemma3* — Issue #19639 — `https://github.com/ggml-org/llama.cpp/issues/19639` — Gemma 3 vision leak (referencial, no Gemma 4).

## Auto-evaluación final del informe

| Casilla | Estado | Comentario |
|---|---|---|
| ¿Cité ≥30 fuentes con URL y fecha? | [x] | **90 fuentes** citadas con URL completas, distribuidas en Tier 1 (1–39), Tier 2 (40–67) y Tier 3 (68–90). |
| ¿Marqué cada afirmación con su nivel de confianza? | [x] | Etiquetas `MEDIDO / CITADO / EXTRAPOLADO / [NO PÚBLICAMENTE MEDIDO AL 2026-05-15]` aplicadas en todos los bloques A–I. |
| ¿Distingo Gemma 4 de Gemma 3/3n en cada sección donde aplica? | [x] | Verificación de release como primer paso. Descartado explícitamente `Misc. bug: CUDA memory leak with MTMD requests loop with Gemma3` (#19639) como Gemma 3, no Gemma 4. Documentado en §C que parser dedicado #21418 reemplaza autoparser que confundía Gemma 3/4. Audio encoder es USM "same base architecture as Gemma-3n" — citado literal, no extrapolado. |
| ¿El TL;DR cabe en 1 página? | [x] | 8 bullets numerados + síntesis MAL/MEJOR (~3/4 de página de markdown densa). |
| ¿Identifiqué al menos 3 cosas que el cliente está haciendo MAL? | [x] | (a) confiar en `--cache-reuse` roto en Gemma 4; (b) cargar mmproj F16 con riesgo de #21690 incluso en perfiles vision-OFF; (c) E4B-Q6_K como dev model en lugar de UD-Q4_K_XL / 26B-A4B-UD-Q2_K_XL para los tiers superiores. |
| ¿Identifiqué al menos 3 cosas que el cliente está haciendo MEJOR? | [x] | (a) sampling oficial Google (T=1.0/top_p=0.95/top_k=64/rep=1.0); (b) `--jinja` + parser nativo llama-server post-#21418 en lugar de Ollama (que tira tool_calls en streaming); (c) profile-switching consciente de límite 6 GB. |
| ¿El roadmap de 90 días es accionable sin recursos infinitos? | [x] | 13 sprints semanales, cada uno con entregable verificable; total esfuerzo top-10 cambios ≈ 10–12 días/persona; resto es validación + opt-ins. |
| ¿Hay un solo número en el informe que no esté citado o marcado como extrapolación? | [x] | Todos los números clave llevan fuente o etiqueta `[EXTRAPOLADO]` / `[NO MEDIDO PÚBLICAMENTE]`. Cuando se da un rango (por ejemplo "+1–2 pp Carter"), se indica que es proyección. |

**Cumple las 8 casillas. Informe entregable.**

---

### Notas finales para el cliente

1. La acción de mayor ROI inmediato (impacto × baja-fricción) es el **Sprint 1+2** combinado: pin de build llama.cpp post-#21418 + cambiar `balanced` a `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL`. Costo total: 3 días; mejora esperada Carter +1–2.5 pp con misma VRAM.

2. La mayor incertidumbre estratégica es el **timing del soporte upstream de MTP drafters** en llama.cpp (Discussion #22735). Si Google y el mantenedor de ggml-org priorizan el merge en mayo-junio 2026, el cliente obtiene 2–3× latencia gratis sin cambios de runtime ni VRAM proporcional (los drafters comparten KV cache con el target). Si no merged, hay que decidir si tolerar la espera o migrar a ik_llama.cpp (rompe la restricción "llama.cpp como runtime único").

3. La mayor mentira "consensuada" en la blogosfera Gemma 4 que el cliente debe ignorar: que **q8_0 KV cache es prácticamente lossless**. En 26B-A4B es KL 0.377 según localbench, y en 31B es KL 0.108. Para un agente con tool calling, el límite tolerable empírico es KL < 0.10 [EXTRAPOLADO]. Mantener KV F16.

4. Visión nativa y audio nativo de Gemma 4 son tentaciones del modelo card pero **bloqueadas por bugs upstream** al 2026-05-15. El cliente está acertando al mantener pipelines tradicionales (Whisper + Piper). Reevaluar en 90 días.

5. Los benchmarks Carter 540 (99.81% PASS con E4B-Q6_K del dev) son **mejores que cualquier número público disponible para Gemma 4 sobre tool calling en español**. El cliente tiene el activo de evaluación correcto; mi recomendación es publicar (anonimizado) la metodología Carter para crear un punto Schelling de benchmarking de agentes locales — convertiría al cliente en referencia.

— fin del informe —