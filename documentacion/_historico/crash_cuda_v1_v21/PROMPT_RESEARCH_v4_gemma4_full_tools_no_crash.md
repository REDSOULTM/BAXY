# PROMPT v4 — Solución directa al bug CUDA Gemma 4 + SWA + flash-attn, SIN sacrificar tools del agent

## El objetivo (lo importante)

**Quiero que el agent pueda exponer TODAS sus tools** (≥66 en el catálogo) **al LLM sin que el server crashee, sin caps artificiales del subset, sin pausa perceptible al usuario.**

El bug actual obliga a limitar el subset a 5 tools por turn para mantener el prompt bajo ~12k tokens, porque con prompts ≥13k el CUDA peta. Eso significa que **el agent no puede manejar pedidos que requieran tools fuera de ese subset chico** — el LLM ni las ve, no puede llamarlas. Es una castración funcional.

Tu trabajo: encontrar la solución que me permita **subir el cap de tools a 8, 15 o ilimitado** sin que el LLM crashee.

## Lo que NO me sirve (ya descartado)

| Vía | Por qué no |
|---|---|
| Reducir subset a 5 tools | **Es exactamente lo que quiero evitar.** |
| Compactar tool schemas (menos chars por tool) | Solo mueve el techo, no lo elimina. Con 30 tools sigo cerca de los 13k. |
| Workaround defensivo (recovery, caps, retry) | Ya implementado. Esconde el problema, no lo resuelve. |
| Parchar binario local con `skip create_checkpoint` | Plan B documentado, requiere mantener fork; quiero alternativas. |
| Migrar de Gemma 4 a Llama/Qwen | Restricción dura del usuario. **NO.** |
| Cloud / APIs pagas | Restricción dura. **NO.** |

## Estado verificado del bug (2026-05-28)

- **Issue [#22527](https://github.com/ggml-org/llama.cpp/issues/22527)** ABIERTO, sin maintainer engagement.
- Stack trace: `ggml/src/ggml-cuda/ggml-cuda.cu:3083` → `ggml_backend_cuda_synchronize`.
- Trigger reproducible: prompt ≥13k tokens con flash-attn on + Gemma 4 SWA, en la transición prompt-processing → generation.
- Build actual: **b9090** (commit `5757c4dcb178a01c85234a6db7503b19c9598873`).
- Hardware: RTX 4060 Ti 16 GB, CUDA 13.0.88, Windows 11.
- Modelo: `gemma-4-E2B-it-Q4_K_M.gguf` (contexto 16384).

**Causa raíz identificada (corrobórala, no la asumas):**

Gemma 4 tiene arquitectura híbrida con **head sizes mixtos** (no-SWA: `n_embd_head_k = 512`; SWA: `n_embd_head_k_swa = 256`) y **shared KV cache**. El callsite del crash es `create_checkpoint` en `tools/server/server-context.cpp:1968` → `update_tgt` → `llama_state_seq_get_data_ext(... PARTIAL_ONLY)` → kernel CUDA que asume tamaño de head uniforme → access pattern inválido.

Fuentes que lo respaldan:
- [Paweł Huryn on Gemma 4 shared KV](https://x.com/PawelHuryn/status/2042276953470931197)
- [Botmonster: Gemma 4 architecture](https://botmonster.com/posts/gemma-4-architecture-per-layer-embeddings-shared-kv-cache-dual-rope/)
- [Issue #21468 (cache-reuse Gemma 4)](https://github.com/ggml-org/llama.cpp/issues/21468)
- [Issue #21690 (checkpoints OOM)](https://github.com/ggml-org/llama.cpp/issues/21690)

## Métricas que tenés que respetar

| Métrica | Target |
|---|---|
| Subset de tools que el LLM "ve" por turn | **≥30 ideal, ≥15 aceptable, 8 mínimo viable** |
| Tokens del prompt en el caso peor | Cualquiera (incluso 16k) sin crashear |
| Crashes CUDA visibles en 50 turns variados | **0** |
| Latencia turn conversacional (sin tool real) | ≤2s (referencia v21: 0.5-3s) |
| Latencia turn con tool real | ≤10s (referencia v21: 8.8s) |
| Cache hit rate (prefix-cache de llama.cpp) | ≥70% (degradación aceptable: caer a 50% si compensa con bug eliminado) |

## Cosas YA medidas que NO funcionan (no repetir, citalas si las desafiás)

| Vía | Resultado medido |
|---|---|
| `--ctx-checkpoints 0 + --cache-ram 0 + --no-cache-idle-slots` (Plan A) | 4/6 crashes visibles con subset grande |
| `--batch-size = ctx-size = 16384` (eliminar shifts intermedios) | Compute buffer 532 MiB → 17 GB, OOM en 4 GB VRAM. Y el crash dispara igual con el prompt en una sola pasada. |
| `--cache-reuse 256` con prompts grandes | Empeora — `memory_seq_rm` shifting también dispara CUDA (#17109) |
| `--no-flash-attn` | OOM por V cache padding mismatched |
| `--no-swa-full` | Pierde cache hit + bug #21468 |
| `--ctx-size 8192 / 6144` | Crash igual |
| `GGML_CUDA_GRAPHS=OFF` compilado-in | NO arregla (#22527 verbatim) |
| `q8_0` KV cache | OOM |
| Downgrade build < b8607 | NO carga Gemma 4 |
| ik_llama.cpp fork | Mismo bug (issue #1693) |
| vLLM con GGUF | "Highly experimental and under-optimized" según doc oficial |

## Ejes a investigar

### Eje 1 — Reducir el peso de los tools en el prompt sin cortar el catálogo

Esto es probablemente la vía más fértil. El problema concreto es que el `tools=[...]` del body OpenAI-compat + el bloque "EXTRA TOOL RULES" + el system prompt se SUMAN. 30 tools full = 14k tokens; 30 tools compact = 7k tokens. Hay margen.

1. **¿Hay una representación de tools más compacta que el JSON schema completo OpenAI-compatible que llama.cpp acepte?** Por ejemplo TypeScript signature, función con docstring, formato Anthropic XML tools, o un formato custom. Si llama.cpp con `--jinja` permite override del template, podría inyectar tools en un formato 3× más corto. Investigá.
2. **¿Hay un "tool dictionary" cacheable**? Si el system prompt + tool schemas fueran 1 mensaje fijo (idéntico turno a turno) y el cache-reuse / prefix-cache de llama.cpp lo capture, el reprocess sería 0 — y como nunca cambia, no dispara el path del bug que es sensible al tamaño total nuevo procesado. Verificá si esto es posible con `--cache-reuse N` + system message estable.
3. **¿Tool-routing en 2 fases (router cheapo + caller con subset)?** Una llamada barata con un mini-prompt que clasifica intent → segunda llamada con subset relevante. La primera nunca cruza umbral. Reportá si funciona en producción con Gemma 4 + llama.cpp y costo de latencia.

### Eje 2 — Eliminar el path culpable sin disable flash-attn entero

4. **¿Existe un build de llama.cpp con kernels CUDA "robustos al head mismatch"?** Por ejemplo, llama.cpp tiene flags compilados-in (`GGML_CUDA_F16`, `GGML_CUDA_DMMV_X`, etc.) y backends alternativos (cuBLAS, cuDNN). Investigá si compilando con `-DGGML_CUDA_USE_CUDNN=ON` o equivalente, el kernel CUDA que peta se reemplaza por uno que sí maneja heterogeneidad.
5. **¿Hay variantes del kernel flash-attn en llama.cpp?** `ggml-cuda/fattn-vec-f16.cu`, `fattn-tile-f16.cu`, etc. Identificá cuál se selecciona para Gemma 4 hoy y si forzar otro (vía macro o env var) evita el bug. Documentá la macro exacta.
6. **¿CUDA 12.6 vs 13.0?** Estoy en 13.0.88. Buscá reportes de #22527 / #21690 con CUDA 12.x para ver si la versión del toolkit cambia el síntoma. Si hay diferencia clara, cambiar toolchain es factible.

### Eje 3 — Variantes del modelo que no tengan el head mismatch

7. **¿Existe un GGUF de Gemma 4 que aplaste los heads al mismo tamaño?** Buscá en HuggingFace si Unsloth, Bartowski, Mradermacher u otros publicaron una variante "uniform-heads" o "kv-merged". Reportá repo + tag + verificá que mantenga calidad razonable (perplexity comparable al oficial).
8. **¿`convert_hf_to_gguf.py` tiene flags para aplanar la arquitectura?** Por ejemplo `--no-shared-kv-layers`, `--uniform-heads`, `--force-full-attention`. Si existen, generar mi propio GGUF localmente sin esos features (a costa de VRAM más alta, pero mi GPU tiene 16 GB).
9. **¿Otra quantización (Q5_K_M, IQ4_XS, BF16)?** El bug es de kernel CUDA, no de quantización, pero verificá si hay reportes de que con BF16 (no cuantizado) NO se dispara. Si es así, BF16 entra en 16 GB para E2B.

### Eje 4 — Backends alternativos para llama.cpp

10. **¿Llama.cpp soporta backend Vulkan estable en RTX 40 con Gemma 4?** Vulkan es independiente del path CUDA culpable. Reportá comando de build y si soporta flash-attn equivalente.
11. **¿SYCL / oneAPI?** Mismo argumento, distinto runtime que CUDA.
12. **¿HIP / ROCm con compatibility layer en NVIDIA?** Muy probablemente sí pero verificá si vale el setup.

### Eje 5 — Backends fuera de llama.cpp

13. **¿`text-generation-inference` (HuggingFace TGI) con Gemma 4 GGUF en GPU local?** OpenAI-compatible, requiere docker, free. Verificá si tiene el bug.
14. **¿`MLC-LLM` con Gemma 4?** Compila el modelo a TVM, kernels propios, NO usa el path CUDA de ggml. ¿Soporta tool calling OpenAI-compatible? ¿Corre en Windows o solo Linux/WSL?
15. **¿`ExLlamaV2`?** Soporta Gemma 4? Tool calling?
16. **¿`sglang` o `lmdeploy` localmente?** Mismo cuestionario.

### Eje 6 — Llama.cpp upstream — buscar PRs en vuelo

17. **PRs abiertos al 2026-05-28** que mencionen Gemma SWA, head mismatch, hybrid KV, checkpoint, #22527. Listá los 5 más relevantes con: autor, estado (draft/ready), última actividad, qué archivos toca, si lo puedo cherry-pick a b9090.
18. **¿Algún maintainer (ggerganov, slaren, JohannesGaessler, compilade) comentó algo sobre el bug en otros issues o discussions?** Buscá referencias cruzadas.

## Forma de la respuesta

Para cada solución propuesta:

1. **Nombre corto.**
2. **¿Cuántas tools podría exponer al LLM con esto?** (esa es LA métrica que importa).
3. **¿Por qué elimina el crash?** Mecanismo concreto.
4. **Fuentes** (links + citas verbatim si aplica).
5. **Pasos de implementación** (comandos verbatim).
6. **Costo** (horas, disco, VRAM extra).
7. **Trade-offs** (qué se pierde — latencia, calidad, complejidad).
8. **Cómo validar** (gate verificable).

Al final, **ranking por capacidad de tools desbloqueada / costo de implementación**. Recomendá la #1.

## Honestidad esperada

- Sin fuentes sólidas → marcala como hipótesis.
- Si una vía requiere >8h → anotala pero NO la rankees como #1.
- Si descubrís que algo de "lo ya descartado" merece revisión → reportalo.
- Si la honesta conclusión es "el cap de 5 tools es lo mejor que se puede hoy", decílo. Pero esa conclusión requiere haber descartado las 18 vías de arriba con evidencia, no por intuición.

## Lo que NO quiero como respuesta

- "Aplicá el Plan A con `--ctx-checkpoints 0`" — ya está.
- "Reducí el system prompt" — ya está, los tools son el grueso.
- "Migrá a Qwen" — restricción dura.
- "Usá APIs en la nube" — restricción dura.
- "Esperá a que llama.cpp lo arregle" — eso lo decidimos nosotros, no la respuesta.

---

**Cierre:** la respuesta más valiosa es una solución que me devuelva el catálogo completo de tools al LLM con 0 crashes y sin parchar binarios localmente. Si no existe HOY, una confirmación rigurosa de que no existe (con las 18 vías descartadas con evidencia) también vale.
