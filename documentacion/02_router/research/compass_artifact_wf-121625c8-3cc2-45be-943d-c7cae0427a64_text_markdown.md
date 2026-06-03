# Cómo exponer el catálogo COMPLETO de tools (≥66) a Gemma 4 en llama.cpp sin el crash CUDA "illegal memory access"

## TL;DR
- **La respuesta #1 que devuelve el catálogo COMPLETO (66+ tools) con 0 crashes y sin fork del binario es el "two-phase tool routing" del lado del cliente** (un router barato clasifica la intención y una segunda llamada envía solo el subconjunto relevante), combinado con **compresión de la representación de tools vía `--chat-template-file`** (mecanismo verificado: la plantilla Gemma renderiza `{{ tools | tojson }}`). El routing mantiene el catálogo entero disponible mientras ningún prompt cruza nunca el umbral de ~13k tokens que dispara el crash.
- **El crash es intrínseco al kernel CUDA de flash-attention de Gemma 4 con head sizes mixtos (512/256), NO solo al path de create_checkpoint**: por eso `--ctx-checkpoints 0` falla 4/6. La única forma fiable de evitarlo dentro de llama.cpp+CUDA+FA+Gemma 4 es mantener el prompt por debajo del umbral; ningún flag lo "arregla" a tamaño grande.
- **Alternativa de backend sin fork y sin nube que conserva Gemma 4: ExLlamaV3 + TabbyAPI (EXL3)**, que usa kernels CUDA propios (no ggml) y soporta tool calling OpenAI-compatible. Es la mejor vía si se quiere el catálogo completo en un solo prompt grande, a costa de >8h de setup y conversión de quant.

## Key Findings

### Estado del bug (corroborado, 2026-05-28)
- **Issue #22527** (https://github.com/ggml-org/llama.cpp/issues/22527): abierto por **Xuan-GUo el 29-abr-2026**, **SIN comentarios, sin labels, sin assignees, sin PRs vinculados** — confirmado: ningún maintainer ha respondido. Cita textual: *"The server crashes with CUDA error: an illegal memory access was encountered consistently after the second SWA KV cache context checkpoint is created, during the first completion request."* Crash en `ggml/src/ggml-cuda/ggml-cuda.cu:3083` → `ggml_backend_cuda_synchronize` → `cudaStreamSynchronize`. Hardware: RTX 4060 Ti 16GB, Windows. Cita textual sobre la causa: *"The non-SWA layers use n_embd_head_k = 512 while SWA layers use n_embd_head_k_swa = 256."*
- **PR #21309** (ngxson, "model: support gemma 4"): confirmado. Introduce el ISWA dual-cache (ratio 5:1 SWA:global), `head_dim` variable (256 SWA / 512 global), MoE 128 expertos top-8. Es el origen de la arquitectura de head mixto.
- **Issue #21468** confirmado: "cache reuse is not supported for Gemma 4 models despite -fa enabled and --swa-full".
- **Issue #17109** confirmado: CUDA illegal memory access durante K-Shift (`llama_memory_seq_rm`).
- **ik_llama.cpp #1693** confirmado: "Gemma-4 MoE IQ4_XS: NaN logits → sampling crash / CUDA illegal memory access" en RTX 4060 — el fork tiene el mismo tipo de fallo.
- **Default de los flags de checkpoint** (corrobora la hipótesis del usuario): `--ctx-checkpoints` default = 32 en master (8 en algunos mirrors antiguos); `--checkpoint-every-n-tokens` default = **8192** (se crea un checkpoint cada 8192 tokens DURANTE el prefill de un único prompt nuevo); `--checkpoint-min-spacing-nt` default = 256. **Esto confirma que el crash se dispara procesando un prompt nuevo grande, independientemente de los turnos**, porque a ≥13k tokens ya se han creado ≥2 checkpoints en el propio prefill. Y como `--ctx-checkpoints 0` igual crashea 4/6, el kernel FA de head mixto también falla en la transición prefill→generación por sí mismo.

### Mecanismo clave que habilita la solución #1 (verificado)
La plantilla Jinja de llama.cpp **sí** controla la serialización de tools. Con `--jinja`, los tools del array OpenAI-compat se renderizan dentro de la plantilla; la plantilla DeepSeek usa `{{tools | map(attribute='function') | tojson(indent=2)}}` y las plantillas Gemma/EXAONE usan `{{ tools | tojson }}` o `{%- for tool in tools %}<tool>{{ tool | tojson }}</tool>`. Por tanto, un `--chat-template-file` custom puede inyectar los tools en un formato 2-3× más corto (firma TypeScript, formato compacto tipo TOON, o schema podado). Datos del propio usuario: 30 tools full = 14k tokens; 30 tools compact = 7k tokens.

## Details — los 18 avenues por eje

### EJE 1 — Reducir el peso de los tools sin recortar el catálogo (la vía más fértil)

**Avenue 1 — Representación compacta de tools vía `--chat-template-file`**
1. Nombre: Compresión de schema en la plantilla Jinja.
2. Tools expuestos: **sube de 5 a ~15-30 por turno** (compresión ~2× medida por el usuario: 14k→7k para 30 tools). El orden de magnitud está respaldado por la literatura: TOON (Token-Oriented Object Notation, toonformat.dev) reporta *"~40% fewer tokens in mixed-structure benchmarks across 4 models"* (InfoQ nov-2025: *"55% reduction in tokens vs. pretty-printed JSON, 25% vs. compact JSON, and 38% vs. YAML"*); y la compresión de contexto de tools de Xu et al. (arXiv:2407.02043, "Concise and Precise Context Compression for Tool-Using Language Models") *"reaches a performance comparable to the upper-bound baseline under up to 16x compression ratio"* en API-Bank y APIBench.
3. Por qué evita el crash: reduce los tokens del prompt por debajo del umbral de ~13k. No toca el kernel; ataca la causa práctica (tamaño del prompt).
4. Fuentes: docs `function-calling.md` de llama.cpp (las plantillas renderizan `tools | tojson`; verbatim: *"Use --chat-template-file to override the template when appropriate"*); toonformat.dev / InfoQ (TOON); arXiv:2407.02043 (Xu et al.).
5. Pasos: crear `gemma4-compact.jinja` que itere los tools y emita solo `name`, `description` truncada y parámetros requeridos en una línea por tool; arrancar con `llama-server --jinja --chat-template-file gemma4-compact.jinja ...`. Verificar el render en `http://localhost:8080/props` (`chat_template`).
6. Coste: 2-4h. 0 disco/VRAM extra.
7. Trade-offs: descripciones más cortas pueden reducir la accuracy de selección de tool; hay que testear. Riesgo de romper el parser nativo gemma4 (cae a "Generic" y consume más tokens, contraproducente) — validar que el log sigue mostrando `Chat format: peg-gemma4`.
8. Validación: contar tokens del prompt renderizado; gate = ≤13k con N tools; 50 turnos sin crash.

**Avenue 2 — Diccionario de tools cacheable como prefijo estable**
1. Nombre: Prefix cache / `--cache-reuse` del bloque fijo de tools.
2. Tools expuestos: no aumenta el cap por sí solo; reduce latencia.
3. Por qué (NO) evita el crash: el crash se dispara en el PRIMER procesamiento del prefijo grande (durante el prefill). Cachear no evita ese primer pase. Además #21468 documenta que cache-reuse no está soportado para Gemma 4 con -fa; #15082 reporta cache-reuse roto en builds recientes; el comentario del usuario en #22354 muestra que cualquier cambio en el prefijo invalida todo.
4. Fuentes: Discussion #8947 (`--system-prompt-file` cachea prefijo común), #20574 (host-memory cache), #13606 (slots), #21468, #15082.
5. Pasos: `--system-prompt-file tools.txt -np 1 --cache-ram N`, mismo bloque de tools en cada request.
6. Coste: 1-2h.
7. Trade-offs: NO resuelve el crash; solo ayuda a latencia si se queda bajo el umbral. Por sí solo es insuficiente.
8. Validación: log `cache_hit` / `n_past` con tokens reusados.
**Veredicto: descartado como solución del crash; útil solo como complemento de latencia.**

**Avenue 3 — Two-phase tool routing (cliente) — LA RESPUESTA #1**
1. Nombre: Router barato + caller con subconjunto.
2. Tools expuestos: **catálogo COMPLETO ilimitado (66+).** El LLM nunca ve >N tools en un mismo prompt, pero el catálogo entero está disponible vía el router.
3. Por qué evita el crash: el prompt enviado a Gemma 4 nunca cruza el umbral de ~13k tokens, así que el kernel FA de head mixto nunca entra en el estado que crashea, con o sin checkpoints.
4. Fuentes: patrón estándar (Arize "Best Practices for Building an Agent Router"; lamini-ai/llm-routing-agent); **NousResearch/hermes-agent #6839** "Lazy Tool Schema Loading — Two-Pass Tool Injection" documenta exactamente esto y mide que los tools formateados son **10× más lentos** en local (*"1,230 tok/s vs 134 tok/s with 8 tools"*); Xu et al. (arXiv:2407.02043) y TinyAgent describen "loading only query-relevant tools"; OpenAI documenta *"tool search so deferred tools are loaded only when needed."*
5. Pasos: (a) llamada 1 = mini-prompt sin tools o con un único tool `route(query)→[tool_names]` que clasifica intención; (b) el cliente arma un subconjunto de ≤15 tools y hace la llamada 2 real. Mantener un índice estático de los 66 tools en el cliente.
6. Coste: 4-8h de código del lado del cliente. 0 VRAM/disco.
7. Trade-offs: +1 llamada barata por turno (~1-2s con E2B; cumple ≤2s conversacional y ≤10s con tool real). El router puede equivocarse de subconjunto → mitigable con few-shot e índices por dominio.
8. Validación: 50 turnos variados, 0 crashes, ≥70% cache hit en el prefijo compartido del router; tasa de acierto de routing ≥90%.

### EJE 2 — Eliminar el path culpable sin desactivar flash-attn

**Avenue 4 — Build con cuDNN flash-attention robusto a head mismatch**
2. Tools: N/A (no cambia capacidad).
3-4. llama.cpp NO tiene un backend cuDNN-FA que reemplace el kernel ggml. El FA de CUDA en ggml usa kernels propios (`fattn-*.cu`). No hay `-DGGML_CUDA_USE_CUDNN` que cambie el path del crash. **Hipótesis descartada por falta de evidencia de tal flag.**
6-8. N/A.

**Avenue 5 — Forzar otra variante del kernel FA**
2. Tools: N/A.
3. ggml tiene `fattn-vec-f16.cu`, `fattn-tile-f16.cu`, `fattn-mma-f16.cu`. El selector elige según head size; para Gemma 4 con head 512/256 entra el path que crashea. No hay env var pública documentada (`GGML_CUDA_FA_ALL_QUANTS` afecta a build de quants, no al selector de tile). El merge-note de TurboQuant cita "#20998: FA support for head dim 512" y exclusiones de head_dim 512 en `fattn.cu` — indica que el manejo de head 512 es especial y frágil.
4. Fuentes: DeepWiki "Flash Attention and Optimizations"; discusión TurboQuant #21526.
6-8. Requeriría editar el selector y recompilar = fork. **Descartado como #1 (es patch de binario).**

**Avenue 6 — CUDA 12.6 vs 13.0/13.2**
2. Tools: N/A.
3. Relevante y reforzado: Unsloth advierte explícitamente **"Do NOT use CUDA 13.2 runtime for any GGUF as it will cause poor outputs"** (doc oficial "Gemma 4 - How to Run Locally", unsloth.ai/docs/models/gemma-4). danielhanchen (Unsloth) amplía en la discusión de HF (gemma-4-31B-it-GGUF #12): *"Using CUDA 13.2 can lead to gibberish or otherwise incorrect outputs, and tool calling may break on Gemma 4, GLM-5.1, and all models. We've confirmed this internally, and the issue has also been reported by llama.cpp and 30+ users... We notified NVIDIA 5–6 days ago."* El reporter de #22527 está en CUDA 13.2; el usuario está en 13.0.88 (mejor pero no 12.x). Bajar a CUDA 12.x es un experimento barato.
4. Fuente: Unsloth docs + danielhanchen (HF).
5. Pasos: usar build `llama-*-cuda-12.x` y driver compatible; re-test del soak de 50 turnos.
6. Coste: 1-2h.
7. Trade-offs: posible leve baja de rendimiento; NO garantiza eliminar el illegal-access (es bug de kernel, no de toolkit; afecta sobre todo a corrección de salida/tool calling).
8. Validación: 50 turnos a ≥13k tokens. **Vale la pena probar por bajo coste, pero no es #1.**

### EJE 3 — Variantes del modelo sin head mismatch

**Avenue 7 — GGUF de Gemma 4 con heads uniformes**: No existe repo conocido (Unsloth/Bartowski/Mradermacher publican el modelo estándar con la arquitectura ISWA original). **Hipótesis: no existe.** Aplanar heads cambiaría la arquitectura del modelo y rompería los pesos.
**Avenue 8 — Flags en `convert_hf_to_gguf.py`**: No existen flags `--no-shared-kv-layers`/`--uniform-heads`/`--force-full-attention` en el conversor. **Hipótesis descartada.**
**Avenue 9 — Otra cuantización (Q5_K_M, IQ4_XS, BF16)**: El crash es bug de kernel CUDA, no de quant — confirmado porque #22527 (IQ3_XXS), #1693 (IQ4_XS) y reportes en f16 KV crashean igual. No hay evidencia de que BF16 lo evite; E2B BF16 (~10GB) cabe en 16GB pero es **hipótesis no verificada**. KV cache se mantiene f16 en SWA (no se puede quantizar, #21394).

### EJE 4 — Backends alternativos de llama.cpp

**Avenue 10 — Vulkan backend (NV_coopmat2)**
2. Tools: potencialmente catálogo completo si evita el crash.
3. El crash de #22527 es de path CUDA puro (`ggml_backend_cuda_synchronize`); Vulkan usa shaders distintos, así que NO entraría en ese código. PERO: **no hay ningún reporte que confirme o niegue que el bug subyacente se reproduzca en NVIDIA + Vulkan coopmat2 FA** (los crashes Vulkan de Gemma 4 SWA conocidos —#22842 en AMD RDNA 3.5, #22275 en Intel Arc— son por paths distintos). Además, FA en Vulkan solo existe con NV_coopmat2 en drivers NVIDIA muy nuevos y tiene historial de incoherencia (#11268 "Coopmat2 Flash Attention leads to incoherent output" en RTX 3090).
4. Fuentes: Discussion #12629 (*"Right now flash attention on vulkan is only supported on some NVIDIA drivers with the coopmat2 extension"*), #10879, #11268, Issue #22842.
5. Pasos: build Vulkan (`-DGGML_VULKAN=ON`), driver NVIDIA beta con coopmat2, `llama-server -fa on -dev Vulkan0`.
6. Coste: 3-6h.
7. Trade-offs: FA coopmat2 inmaduro; latencia inferior a CUDA en RTX 4060 Ti; riesgo de output incoherente.
8. Validación: bench de coherencia + 50 turnos a ≥13k. **Hipótesis de alto valor pero NO verificada; probar en paralelo.**

**Avenue 11 — SYCL/oneAPI**: pensado para Intel; madurez baja en NVIDIA. No recomendado. **Descartado.**
**Avenue 12 — HIP/ROCm sobre NVIDIA**: ZLUDA es frágil; los reportes ROCm/HIP de Gemma 4 (#21912) muestran reprocesamiento y crashes equivalentes. **Descartado.**

### EJE 5 — Backends fuera de llama.cpp (conservando Gemma 4, sin nube)

**Avenue 13 — HuggingFace TGI**: TGI corre Gemma 4 (`--model-id google/gemma-4-E2B-it --dtype bfloat16`) con API OpenAI-compatible, pero usa **safetensors**, no GGUF Q4_K_M (desvío del pin del usuario). E2B en bf16 (~10GB) cabe en 16GB. No usa el path ggml CUDA → evita el bug. Coste docker + cambio de formato. **Alternativa válida pero cambia el quant; marcar el desvío del GGUF Q4_K_M.**

**Avenue 14 — MLC-LLM**: **NO soporta Gemma 4** (Issue #3477, *"ValueError: Unknown model type: gemma4"*). **Descartado hoy.**

**Avenue 15 — ExLlamaV3 / TabbyAPI (EXL3) — mejor alternativa de backend**
1. Nombre: ExLlamaV3 + TabbyAPI con quant EXL3.
2. Tools expuestos: **catálogo completo** hasta el límite de contexto (no hay el crash de ggml); en un solo prompt grande.
3. Por qué evita el crash: kernels CUDA propios de ExLlamaV3 (no ggml); maneja head_dim de Gemma 4. El crash de ggml-cuda no aplica.
4. Fuentes: README ExLlamaV3 (verbatim github.com/turboderp-org/exllamav3: *"The Gemma4 implementation benefits greatly from xformers (pip install xformers) which will be autodetected and used when available. Performance is likely to improve further with a better head_dim > 256 attention implementation soon"*); existe `turboderp/gemma-4-31b-it-exl3`; TabbyAPI OAI-compatible con tool calling (open-webui #23863 lo usa con Gemma 4).
5. Pasos: instalar ExLlamaV3 (CUDA 12.4+, VS Build Tools en Windows), convertir/descargar EXL3 de E2B, arrancar TabbyAPI.
6. Coste: **>8h** (build de extensión en Windows + conversión EXL3 + plantilla de tools). VRAM: E2B EXL3 ~3-5GB.
7. Trade-offs: el atención head_dim>256 aún no óptima (perf); ecosistema más nicho; conversión de quant.
8. Validación: tool call OAI + 50 turnos con catálogo completo, 0 crashes.

**Avenue 16 — sglang / lmdeploy**: soportan Gemma 4 vía safetensors en Linux/WSL con tool calling, no usan ggml CUDA. Setup pesado en Windows (WSL). **Alternativa secundaria; cambia formato.** (vLLM con safetensors soporta `--tool-call-parser gemma4`, pero su soporte GGUF es, verbatim docs oficiales docs.vllm.ai: *"GGUF support in vLLM is highly experimental and under-optimized at the moment, it might be incompatible with other features"* — por eso solo el path safetensors es viable, desviándose del GGUF.)

### EJE 6 — PRs upstream en vuelo

**Avenue 17 — PRs abiertos relevantes (cherry-pick sobre b9090)**
- **PR #22929** "server: fix checkpoints creation" (jacekpoplawski, **ABIERTO**, abierto 11-may-2026, 16 commits al 22-may). Cambia la creación de checkpoints a límites de mensaje (message spans) en vez de mid-prompt. Probado con Gemma 4 31B. ggerganov comentó *"Yes, that seems in a good direction. Have you done testing that it works as expected?"* Podría reducir los crashes ligados a checkpoint, pero NO toca el kernel FA → no garantiza eliminar el 4/6 residual. Toca `tools/server/server-context.cpp`. Cherry-pickeable pero = mantener fork.
- **PR #21749** "server: ensure prompt caching for SWA models" (shipped-it): pone `pos_min_thold = 0` con `--swa-full` y salta la restauración de checkpoint. Toca `server-context.cpp`.
- **PR #21513** "kv-cache: support attention rotation for heterogeneous iSWA" (ggerganov, **MERGED 7-abr-2026**, branch `gg/kv-cache-swa-attn-rot`): aborda head sizes mixtos de Gemma 4 (verbatim: *"Support iSWA models with different head sizes in the SWA vs non-SWA layers (such as Gemma 4)"*) pero **sin discusión del crash de illegal-access**; ya está en b9090.
- **Issues #22384 / #22450 / #21831 / #21912**: familia de bugs de checkpoint/reprocesamiento SWA-hybrid, varios con la misma firma `ggml_backend_cuda_synchronize`.

**Avenue 18 — Comentarios de maintainers**: Confirmado que **ningún maintainer (ggerganov, slaren, JohannesGaessler, compilade, ngxson) ha comentado en #22527**. ggerganov sí participó en PR #21513 (head mixto) y PR #22929 (checkpoints). JohannesGaessler (autor del CUDA-FA) no aparece en #22527 ni en la diagnosis del crash de head mixto.

## Ranking por (capacidad de tools desbloqueada / coste de implementación)

| # | Solución | Tools expuestos | Coste | Evita crash | Fork |
|---|----------|-----------------|-------|-------------|------|
| **1** | **Two-phase routing (Avenue 3)** | **Ilimitado (66+)** | 4-8h | Sí (prompt < umbral) | No |
| **2** | **Compresión de template (Avenue 1)** | 15-30/turno | 2-4h | Sí (reduce tokens) | No |
| 3 | ExLlamaV3+TabbyAPI (Avenue 15) | Completo en 1 prompt | >8h | Sí (kernels propios) | No |
| 4 | CUDA 12.x downgrade (Avenue 6) | N/A | 1-2h | Incierto | No |
| 5 | Vulkan coopmat2 (Avenue 10) | Completo (si funciona) | 3-6h | Hipótesis | No |
| 6 | TGI/vLLM/sglang safetensors (13/16) | Completo | docker | Sí | No (cambia quant) |
| 7 | Cherry-pick PR #22929/#21749 (Avenue 17) | parcial | 3-5h | Parcial | Sí |
| — | Cache de prefijo (Avenue 2) | 0 | 1-2h | No | No |
| — | SYCL/HIP, MLC, GGUF heads-uniformes, conversor flags | 0 | — | Descartados | — |

## Recommendations

**Fase 0 (hoy, 1-2h):** Cambiar a un build CUDA 12.x (Avenue 6) por el aviso de Unsloth/danielhanchen sobre CUDA 13.2; el usuario está en 13.0.88, así que el beneficio sobre el crash es incierto (afecta sobre todo a corrección de salida y tool calling), pero es barato y mantiene la base limpia.

**Fase 1 (recomendación #1, 4-8h): Implementar two-phase routing (Avenue 3) + compresión de template (Avenue 1) en conjunto.** Esto devuelve el catálogo COMPLETO de 66+ tools al sistema (disponible vía router, no al LLM en un solo prompt) y eleva el cap por turno de 5 a ~15-30, todo sin fork, sin nube, conservando gemma-4-E2B-it-Q4_K_M.gguf (ctx 16384). El prompt nunca cruza ~13k tokens → 0 crashes. **Es la combinación con mejor ratio capacidad/coste.**
- Benchmark que cambia la recomendación: si tras compresión el prompt de N tools sigue ≥13k, bajar N o profundizar la compresión.

**Fase 2 (si se necesita el catálogo completo en UN solo prompt, >8h): ExLlamaV3 + TabbyAPI (EXL3)** como backend alternativo sin fork de llama.cpp. Probar Vulkan coopmat2 (Avenue 10) en paralelo como experimento de bajo compromiso.

**Umbrales de decisión:**
- Si two-phase routing logra ≥15 tools/turno con 0 crashes y latencia ≤10s → **parar aquí, es la solución**.
- Si se exige ≥30 tools en un único prompt → migrar a ExLlamaV3/TabbyAPI o a un backend safetensors (TGI / vLLM con `--tool-call-parser gemma4`), aceptando el desvío del formato GGUF.
- Plan B (patch local "skip create_checkpoint") solo si todo lo anterior falla; el usuario ya lo tiene documentado y no se recomienda como #1.

## Caveats
- **El crash NO se elimina con flags a tamaño de prompt grande**: confirmado que `--ctx-checkpoints 0` falla 4/6 porque el kernel FA de head mixto también crashea en la transición prefill→generación. La evidencia (checkpoint cada 8192 tokens por default + crash con checkpoints desactivados) confirma que el disparo es el TAMAÑO del prompt (≥13k), no solo el checkpoint.
- **Avenues marcados como hipótesis no verificada**: BF16 evitando el crash (Avenue 9); GGUF con heads uniformes (7) y flags del conversor (8) **no existen**; Vulkan en NVIDIA reproduciendo o no el bug (10) **sin reporte que lo confirme**.
- **Cifras de compresión**: el 2× del usuario (14k→7k) es consistente con TOON (*"~40% fewer tokens"*, hasta 55% vs JSON pretty-printed) y con la compresión de contexto de tools de Xu et al. (hasta 16×). NO pude verificar la referencia "arXiv 2605.26165 / Tscg 44-68%" que aparecía en borradores previos — sustituida por la fuente verificable arXiv:2407.02043. Tratar el rango 44-68% como no confirmado.
- **TGI/vLLM/sglang/ExLlamaV3 cambian el formato del peso** (safetensors o EXL3) respecto al pin gemma-4-E2B-it-Q4_K_M.gguf; conservan el MODELO Gemma 4 pero no el archivo exacto. Marcar como desvío del hard constraint si el pin del GGUF es estricto.
- **Riesgo del template custom**: si rompe el parser nativo gemma4, llama.cpp cae a "Generic" y consume MÁS tokens (contraproducente). Validar `Chat format: peg-gemma4` en el log.
- Defaults de `--ctx-checkpoints` divergen entre master (32) y mirrors antiguos (8) — verificar en el build propio (b9090, commit 5757c4dcb178a01c85234a6db7503b19c9598873).
- **Honestidad final**: **hoy SÍ existe una solución que devuelve el catálogo completo con 0 crashes y sin patchear el binario** — es two-phase routing (capacidad ilimitada del catálogo) y/o ExLlamaV3 (catálogo completo en un prompt). Lo que NO existe es un flag de llama.cpp+CUDA que permita meter los 66 tools en un único prompt Gemma 4 con FA sin crashear.