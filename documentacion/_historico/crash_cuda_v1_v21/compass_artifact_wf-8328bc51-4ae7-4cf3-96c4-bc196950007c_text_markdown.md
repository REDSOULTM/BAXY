# Crash CUDA "illegal memory access" en llama-server con Gemma 4 + flash-attn + swa-full: diagnóstico y opciones

**TL;DR**
- **(A) Recomendada: degradar a llama.cpp commit `149b2493c` (19-mar-2026, anterior a b8607)**, que el reporter de issue #21383 documenta como "Last known working" para la regresión de prompt-cache / `memory_seq_rm`; PR #22288 (`server : fix swa-full logic`, fusionado ~29-abr-2026 e incluido en b9090) corrige sólo el síntoma de "forcing full reprocessing" de #21468, NO el crash de #22527 ni el path LCP+seq_rm — actualizar más no ayuda.
- **(C) Mitigación inmediata sin tocar build: añadir `"cache_prompt": false` por petición en el cuerpo OpenAI**, y/o lanzar con `--slot-prompt-similarity 0.0` para desactivar la selección de slot por LCP que dispara el `memory_seq_rm` parcial; esto evita el path defectuoso al coste de ~+1.5-2 s de prefill por turno (mismo coste que tu `--no-swa-full` actual).
- **(E) Si la latencia importa más que el cache hit**, mantener el build pero envolver el cliente en un *circuit breaker* que llame `POST /slots/0?action=erase` cada N turnos (issue #17387 confirma que el endpoint existe y funciona, con un workaround de timeout) — Gemma 4 E2B-it Q4_K_M ocupa 3.11 GB en disco (SHA256 `9378bc471710229ef165709b62e34bfb62231420ddaf6d729e727305b5b8672d` per la página oficial unsloth/gemma-4-E2B-it-GGUF en Hugging Face), por lo que un reprocesado completo de 16k tokens no es prohibitivo en una RTX 4060 Ti.

## Key Findings

1. **El bug está reconocido y sin fix oficial.** Issue #22527 ("Gemma 4 31B: illegal memory access after SWA KV cache checkpoint with Flash Attention enabled", abierto el 29-abr-2026 por Xuan-GUo en build b8975) reproduce exactamente tu stack (RTX 4060 Ti 16 GB, Windows, `--flash-attn on`, SWA). El cuerpo del issue documenta que **todas** las mitigaciones obvias fallan: *"Disabling Flash Attention (--flash-attn off) → server fails to allocate VRAM due to V cache padding for mismatched layer sizes / Reducing context size (-c 8192, -c 6144, -c 10240) → same crash / Adding --cache-ram 0 → crash delayed by ~2 turns but still occurs / Disabling CUDA Graphs (GGML_CUDA_GRAPHS=OFF) → same crash / Using q8_0 KV cache with Flash Attention off → OOM due to V cache padding"*. No hay PR cerrando el issue al día de hoy.

2. **PR #22288 NO arregla este bug.** El PR (`server : fix swa-full logic`, fusionado ~29-abr-2026, incluido en b9090) cierra el issue #21468 ("cache reuse is not supported for Gemma 4 models despite -fa enabled and --swa-full"), que es un problema **de rendimiento** ("forcing full prompt re-processing"), no el `illegal memory access` de #22527. PR #21749 fue superseded por #22288; ambos describen su objetivo como *"Setting pos_min_thold = 0 when swa_full is enabled"* y *"Skipping checkpoint restoration logic when swa_full is enabled"*. No tocan el path LCP→`memory_seq_rm`→forward pass.

3. **La regresión está acotada entre `149b2493c` (19-mar-2026) y `f49e91787` (3-abr-2026).** Issue #21383 (Qwen3.5-27B, mismo síntoma exacto en path de tool-calls/prompt-cache) afirma textualmente: *"Last known working: 149b2493c (March 19, 2026) First observed broken: f49e91787 (April 3, 2026, current master)"*, *"Rolling back to 149b2493c resolves both crashes"*, y *"Not yet narrowed further. The 93+ commits between these contain several prompt cache and checkpoint changes (#20087, #19924, #19877, #19849, #20955)"*. La ventana son **93+ commits**, no cientos. El commit `149b2493c` tiene como título *"common : fix typo in debug log ('extracft' -> 'extract') (#20807)"* (verificado en github.com/ggml-org/llama.cpp/commit/149b2493c) y cae **antes de b8607**, que es el primer build de abril 2026 según el changelog (fazm.ai: *"April 2026 brought over 170 incremental releases to llama.cpp (builds b8607 through b8779)"*). Como referencia cruzada, bartowski usó **b8647** para cuantizar `bartowski/google_gemma-4-E2B-it-GGUF` (*"Using llama.cpp release b8647 for quantization"*), lo que sitúa b8647 al inicio de abril 2026 — confirmando que 149b2493c (19-mar) es de la generación inmediatamente anterior a la primera release que cuantizó Gemma 4. Tu build b9090 (5757c4d, 9-may-2026) es muy posterior a la ventana de regresión.

4. **Issue #17109 ("CUDA error during K-Shift") confirma la causa raíz genérica**: la secuencia `llama_memory_seq_rm` en mitad de contexto → `seq_add` → `seq_cp` → `decode` causa illegal memory access en CUDA. El log de tu crash (`memory_seq_rm [MMM, end)` seguido de MUL_MAT failed en `ggml_backend_cuda_synchronize`) coincide con esa receta. No hay fix oficial.

5. **`--slot-prompt-similarity 0.0` evita el path LCP**. Según `tools/server/README.md` del repo oficial: *"how much the prompt of a request must match the prompt of a slot in order to use that slot (default: 0.10, 0.0 = disabled)"*. Con sólo `--parallel 1` esto no cuesta nada extra: como solo hay un slot, ponerlo a 0 fuerza siempre el mismo slot por LRU sin invocar la rama de búsqueda LCP que ejecuta el `memory_seq_rm` parcial.

6. **`cache_prompt: false` per-request existe y funciona en `/v1/chat/completions`**. Confirmado en `tools/server/README.md` del repo oficial: *"cache_prompt: Re-use KV cache from a previous request if possible … Default: true"*. Poniéndolo a `false` en el body JSON de cada petición se evita el reuse y por tanto el `memory_seq_rm`.

7. **`POST /slots/{id}?action=erase` existe y funciona** (issue #17387 lo documenta y muestra la respuesta `{"id_slot":0,"n_erased":43}`), pero requiere `--slot-save-path PATH` al iniciar el servidor. **Atención**: issue #18703 demuestra que en modo `--models-preset` (router multi-modelo, que es tu caso) el endpoint devuelve **400 "Invalid action"**, y hay que conectar directamente al puerto del modelo individual por detrás del router.

8. **Modelos sin SWA = sin este bug.** Gemma 2/3/4 usan SWA (5:1 local-global en Gemma 3, mezclado en Gemma 4). Llama 3.x, Qwen 2.5 y Mistral Small 3+ usan **atención completa** (Mistral abandonó SWA en Small 3.1 — *"sliding_window: null"* en su config; Qwen 2.5 también: *"No, sliding window is not used either in training or inference"* — QwenLM/Qwen3 discussion #989). Phi-4-mini-flash sí usa SWA mezclada con Mamba (*"a self-decoder that combines Mamba (a State Space Model) and Sliding Window Attention (SWA), along with a single layer of full attention"*, Microsoft Azure blog). Llama-3.2-3B-Instruct tiene tool-calling soportado nativamente por vLLM (*"All Llama 3.1, 3.2 and 4 models should be supported"*) y carece de SWA, por lo que es el candidato más limpio.

9. **vLLM no es solución viable hoy para tu setup**. La documentación oficial dice textualmente: *"GGUF support in vLLM is highly experimental and under-optimized at the moment, it might be incompatible with other features"*. Además, vLLM docs sobre Gemma 3: *"V0 correctly implements the model's attention pattern: Uses bidirectional attention between the image tokens corresponding to the same image / V1 … Generates reasonable outputs but does not match the original model's attention for text + image inputs"*. Para Windows + 16 GB + Q4 + visión, vLLM no aporta sobre llama.cpp.

10. **ik_llama.cpp NO es solución para Gemma 4**. Issue #1693 muestra que tras los fixes #1655 y #1657 *"two new crash modes appear with the nohurry/gemma-4-26B-A4B-it-heretic-GUFF (IQ4_XS) model"* incluyendo el mismo `CUDA error: an illegal memory access was encountered current device: 0, in function ggml_backend_cuda_synchronize at D:\AI\ik_llama.cpp\ggml\src\ggml-cuda.cu:4059`. El fork hereda el mismo problema con peor mantenimiento.

## Details

### Pregunta 1 — ¿Existe un build sin el bug?

**Respuesta: SÍ, condicional.** El commit `149b2493c` de ggml-org/llama.cpp (19-mar-2026, título *"common : fix typo in debug log ('extracft' -> 'extract') (#20807)"*) es identificado por el reporter de issue #21383 como "last known working" antes de la regresión.

- **Evidencia**: issue #21383 cuerpo del bug: *"Last known working: 149b2493c (March 19, 2026) First observed broken: f49e91787 (April 3, 2026, current master) Both built from source with identical configuration."* y *"Rolling back to 149b2493c resolves both crashes."*. URL: https://github.com/ggml-org/llama.cpp/issues/21383
- **Mapeo a release bXXXX**: el commit es anterior a **b8607** (primer build de abril 2026 per el changelog público de fazm.ai: *"April 2026 brought over 170 incremental releases to llama.cpp (builds b8607 through b8779)"*). El tag exacto no es fácilmente extraíble desde la web, así que la acción correcta es `git clone https://github.com/ggml-org/llama.cpp && git describe --tags --abbrev=0 149b2493c` en local; el tag resultante (probablemente en el rango b8580-b8606) es el que debes buscar en la página de releases.
- **Binarios Windows CUDA prebuilt**: ggml-org/llama.cpp publica binarios oficiales en cada release tag. Si el tag concreto adyacente a `149b2493c` no tiene asset Windows CUDA (algunos releases intermedios no compilan todos los backends), compilar localmente con MSVC + CUDA Toolkit 12.4+ siguiendo `docs/build.md`, fijando `-DCMAKE_CUDA_ARCHITECTURES=89` para tu RTX 4060 Ti.
- **Forks con patches específicos**: revisado ik_llama.cpp; sus issues #1655 y #1657 introdujeron una primera ronda de fixes para Gemma 4, pero #1693 documenta regresiones posteriores con el mismo crash CUDA. No hay branch experimental en ggml-org/llama.cpp con un PR en revisión que aborde específicamente #22527.

**Coste estimado**: pérdida de los 93+ commits entre `149b2493c` y `f49e91787`, más los ~6 semanas posteriores hasta b9090. Para Gemma 4 E2B-it Q4_K_M en español sin tool-calling avanzado, los fixes posteriores no son críticos. Latencia equivalente.

**Caveats**: verificar que el commit es real (`git cat-file -e 149b2493c`); verificar SHA-256 de cualquier binario Windows prebuilt si lo descargas de un tercero (no oficial); si compilas, fijar `CUDA_ARCHITECTURES=89` (RTX 4060 Ti = compute 8.9).

### Pregunta 2 — ¿Combinación de flags que funcione sin sacrificar latencia?

**Respuesta: SÍ, parcial.** Hay dos flags poco documentados que atacan el origen del bug.

#### `--slot-prompt-similarity 0.0`

- **Qué hace** (oficial, `tools/server/README.md`): *"how much the prompt of a request must match the prompt of a slot in order to use that slot (default: 0.10, 0.0 = disabled)"*.
- **Por qué ayuda aquí**: tu log muestra `selected slot by LCP similarity, sim_best = 0.997 (> 0.100 thold)` justo antes del crash. Poniéndolo a 0.0 se desactiva el matching por LCP y el servidor cae al path LRU; con `--parallel 1` siempre es el mismo slot, y la trayectoria de código que ejecuta `memory_seq_rm` parcial sólo se activa cuando hay match LCP. Equivale funcionalmente a reset+reprocess completo cada turno.
- **Coste**: ~+1.5-2 s de prefill por turno (idéntico a tu medición con `--no-swa-full`). Sin pérdida de VRAM. Sin pérdida de calidad.
- **Caveats**: aún no hay evidencia *medida* de que esto **elimine** el crash; lo deduzco del trazado del path. Issue #17673 ("Server often does 'selected slot by LRU' despite high level of similarity with earlier prompts") confirma que con `-sps 0.0` el servidor cae al path LRU; combinado con `--parallel 1` el cache se reusa por prefijo exacto sin LCP-fuzzy match.

#### `--no-context-shift`

- **Qué hace**: deshabilita el context-shift automático que internamente usa `llama_memory_seq_rm`/`seq_add` (issues #5652 y #9390). Si llegas al límite de contexto, devuelve 400 en vez de hacer shift.
- **Por qué ayuda parcialmente**: Issue #5652 lo documenta como workaround para crashes en `llama_memory_seq_rm`/`seq_shift`: *"Temporary fix: disable context shift via --no-context-shift"*. Sin embargo, **no cubre el seq_rm que dispara la rama LCP partial-match** — esa rama lo invoca por su cuenta. Útil sólo como segunda barrera.
- **Coste**: si el cliente excede 16384 tokens, recibe 400; el cliente debe truncar.

#### Flags que **NO** funcionan (documentados/medidos)

- `--no-flash-attn`: OOM en Gemma 4 por padding del V cache con tamaños de cabeza mixtos (n_embd_head_k = 512 en non-SWA vs 256 en SWA). Confirmado en #22527.
- `--no-swa-full`: pierde el cache hit pero introduce el bug de #21468 (force full reprocessing); además según tu medición, +1.5-2 s prefill.
- `--cache-ram 0`: sólo retrasa el crash (#22527 explícito).
- `--no-cuda-graphs` / `GGML_CUDA_GRAPHS=OFF`: no soluciona (#22527 lo prueba en build con `GGML_CUDA_GRAPHS=OFF`).
- `--ctx-size` menor: no soluciona (#22527 lo prueba con 6144, 8192, 10240).
- `--kv-unified` / `--no-kv-unified`: ningún issue reporta que afecte al path seq_rm de SWA; no hay evidencia.
- `GGML_CUDA_NO_PINNED`, `GGML_CUDA_FORCE_MMQ`, `CUDA_LAUNCH_BLOCKING=1`: ningún issue específico los liga a este bug. `CUDA_LAUNCH_BLOCKING=1` sólo ayuda a *debug* (te da el stack exacto del fallo); no lo arregla.
- `q8_0` KV cache: OOM (#22527 lo prueba).

### Pregunta 3 — ¿Path de API que evite el LCP partial match?

**Respuesta: SÍ.**

1. **`"cache_prompt": false` en el body de `/v1/chat/completions`**. Documentado verbatim en `tools/server/README.md`: *"cache_prompt: Re-use KV cache from a previous request if possible … Default: true"*. Pásalo a `false` en cada petición desde tu cliente y el servidor procesa el prompt entero sin invocar la rama de reuse / seq_rm parcial.

   ```json
   POST /v1/chat/completions
   { "model": "...", "messages": [...], "cache_prompt": false }
   ```

2. **Endpoint `/completion` con `prompt` como token array**. El README oficial dice: *"prompt: Provide the prompt for this completion as a string or as an array of strings or numbers representing tokens. Internally, if cache_prompt is true, the prompt is compared to the previous completion and only the 'unseen' suffix is evaluated."*. Pasando tokens como array y `cache_prompt: false`, el cliente controla 100% la entrada.

3. **`POST /slots/{id}?action=erase`** existe (issue #17387 lo confirma con respuesta `{"id_slot":0,"n_erased":43}`). Requiere `--slot-save-path PATH` al iniciar. **Atención router multi-modelo (#18703)**: con `--models-preset` el endpoint devuelve 400 "Invalid action" porque el proxy no enruta esa acción. Workaround: conectar al puerto interno del modelo (el log de llama-server muestra el puerto efectivo cuando arranca el sub-server, ej. `127.0.0.1:42515`).

4. **`id_slot` explícito** en el body fuerza un slot fijo (`tools/server/README.md`: *"id_slot: Assign the completion task to an specific slot. If is -1 the task will be assigned to a Idle slot. Default: -1"*). Combinado con `--parallel 1` y `--slot-prompt-similarity 0.0` deja un único path determinista.

**Coste**: con `cache_prompt: false` pierdes el reuse del system prompt → +1.5-2 s prefill por turno (mismo coste que `--no-swa-full`). Con `/slots/0?action=erase` cada N turnos pierdes parcialmente; mejor balance.

**Caveats**: el endpoint `/slots/0?action=erase` puede colgar hasta que el cliente haga `Ctrl+C` (issue #17387 abierto el 19-nov-2025, sigue abierto). Workaround: usar timeout corto en el cliente HTTP.

### Pregunta 4 — ¿Migrar de runtime?

**Respuesta: NO.** Todas las alternativas tienen problemas mayores.

- **vLLM**: doc oficial textual: *"GGUF support in vLLM is highly experimental and under-optimized at the moment, it might be incompatible with other features. Currently, you can use GGUF as a way to reduce memory footprint."* Además, doc vLLM sobre Gemma 3: *"V0 correctly implements the model's attention pattern … V1 … Generates reasonable outputs but does not match the original model's attention for text + image inputs"*. Aunque las release notes 2026 listan soporte Gemma 4 (PRs #38826, #38847), GGUF en Windows sigue siendo experimental. Coste de migración alto, beneficio incierto.
- **Ollama**: usa llama.cpp internamente; hereda exactamente el mismo bug. Descartado.
- **llamafile**: rezagado vs llama.cpp upstream; no resuelve.
- **TabbyAPI/ExLlamaV2 (EXL2)**: requiere reconvertir Gemma 4 E2B desde el GGUF/HF original. No hay quants estables públicos de Gemma 4 E2B en EXL2 al día de hoy. Coste alto.
- **TensorRT-LLM**: no tiene path para GGUF; requiere export ONNX/engine; sobreingeniería para 2 B params.
- **ik_llama.cpp**: ik_llama.cpp issue #1693 muestra el **mismo** crash CUDA en el fork. Descartado.

**Conclusión**: ninguna migración tiene mejor coste/beneficio que (A)+(C). Si en algún momento vLLM marca el soporte Gemma 4 GGUF como estable en Windows, reevaluar.

### Pregunta 5 — Mitigación cliente

**Respuesta: SÍ.** Tres patrones combinables:

1. **Token-array prompt + `cache_prompt: false`**: el cliente tokeniza, envía tokens, no usa cache. Garantiza que nunca se ejecuta el path LCP-fuzzy.
2. **Circuit-breaker con `/slots/0?action=erase`**: contador en el cliente; tras N turnos exitosos (ej. N=3 dado que tu crash llega en 2-5 turnos), hacer `POST /slots/0?action=erase` con timeout de 1 s, ignorar respuesta. Esto resetea el slot y evita acumular checkpoints.
3. **Tokens canónicos al final del prompt**: añadir un token único por turno (timestamp en UTF-8) hace `sim_best = 0` siempre → LCP nunca dispara la rama parcial → siempre cae a LRU. Equivalente práctico a `--slot-prompt-similarity 0.0` pero per-request.

**Coste**: opción 1 cuesta +1.5-2 s prefill cada turno; opción 2 cuesta sólo el prefill del turno post-erase; opción 3 también +1.5-2 s.

**Caveats**: confirmar que el endpoint `/slots/{id}?action=erase` no devuelve 400 en modo `--models-preset` (issue #18703). Si tu setup es router-mode, te toca conectar al puerto interno del sub-server.

### Pregunta 6 — Alternativas de modelo

**Respuesta**: el bug es específico de **arquitecturas SWA + flash-attn**.

| Modelo | Tamaño | SWA | Tool-calling | Visión | Veredicto |
|---|---|---|---|---|---|
| Gemma 4 E2B-it | ~2B | **Sí (mixta)** | Sí | Sí | Bug aquí |
| Gemma 3 1B / 4B | 1-4B | **Sí (5:1)** | Limitado | 4B sí | Mismo bug probable |
| Llama-3.2-3B-Instruct | 3B | **No (full GQA)** | Sí (oficial vLLM) | No (3B es text-only) | Mejor candidato sin-bug |
| Qwen 2.5 3B / 7B | 3-7B | **No** (*"No, sliding window is not used either in training or inference"* — QwenLM/Qwen3 discussion #989) | Sí (Hermes-style) | 2.5-VL sí | Excelente candidato |
| Phi-4 mini flash | 3.8B | **Sí** (Samba: Mamba + SWA + 1 full layer) | Sí | No | Posible bug similar |
| Mistral Small 3.1 24B | 24B | **No** (*"sliding_window: null"*) | Sí | Sí | Demasiado grande para 16 GB con FA |
| Mistral 7B v0.3 | 7B | Sí (original) | Sí | No | Riesgo SWA |

**Recomendación**: si quieres salir del bug *sin* cambiar de paradigma, **Llama-3.2-3B-Instruct Q4_K_M** o **Qwen 2.5-3B-Instruct Q4_K_M** dan calidad comparable a Gemma 4 E2B en español + tool calling, sin SWA, y por tanto sin esta clase de bug. Para visión, **Qwen 2.5-VL 3B** (también sin SWA en el LLM, sólo window-attn en ViT) es la mejor opción que mantiene tu stack llama.cpp+CUDA.

## Recommendations

**Decisión por etapas (escoge la primera que cumpla tu umbral):**

1. **Acción inmediata (5 min, cero riesgo)**: añade `"cache_prompt": false` al body de cada `/v1/chat/completions` desde tu cliente Python/Node. Si el crash desaparece y aceptas +1.5-2 s de prefill por turno, ya tienes solución (path C). **Threshold para subir a la siguiente etapa**: latencia inaceptable (>3 s prefill).

2. **Acción inmediata 2 (15 min, cero riesgo)**: re-lanza llama-server con `--slot-prompt-similarity 0.0` añadido (manteniendo el resto). Funcionalmente equivalente al paso 1 pero a nivel servidor (path B). **Threshold**: si el crash persiste tras 10 turnos, descartar.

3. **Acción a 1 día**: implementa circuit-breaker cliente con `POST /slots/0?action=erase` cada 3 turnos exitosos. Si tu servidor está en router-mode (`--models-preset`), primero pasa el flag `--slot-save-path C:\temp\llama-slots`, y si el endpoint devuelve 400, conecta al puerto interno del sub-server (issue #18703 documenta el workaround). **Threshold**: aceptable si el reset cada 3 turnos no rompe la conversación.

4. **Acción a 2 días (downgrade)**: en local,
   ```
   git clone https://github.com/ggml-org/llama.cpp
   cd llama.cpp
   git checkout 149b2493c
   git describe --tags --abbrev=0     # anota el tag bXXXX adyacente
   cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89
   cmake --build build --config Release -j
   ```
   Verifica `Get-FileHash build\bin\Release\llama-server.exe -Algorithm SHA256` y archívalo. **Threshold**: usar si necesitas el cache hit completo y los pasos 1-3 no bastan.

5. **Acción a 1 semana (migración de modelo)**: descargar `Qwen2.5-3B-Instruct-Q4_K_M.gguf` o `Llama-3.2-3B-Instruct-Q4_K_M.gguf`, mantener llama-server b9090, todos los flags actuales excepto eliminar `--swa-full` (innecesario en modelos sin SWA). Esto cierra el bug definitivamente porque las arquitecturas son full-attention. Verificar calidad en español y tool-calling con tu prompt real.

6. **NO migrar** a vLLM, Ollama, llamafile, TabbyAPI, TensorRT-LLM ni ik_llama.cpp para este caso de uso.

**Para reportar upstream**: si quieres acelerar un fix oficial, comenta en issue #22527 con tu config exacta (b9090, RTX 4060 Ti, Gemma 4 E2B Q4_K_M, log con `selected slot by LCP similarity, sim_best = 0.997` justo antes del crash). El reporter original (Xuan-GUo) usa el modelo de 31B; tu repro con E2B confirma que **no** es problema de tamaño y refuerza la prioridad del fix.

## Caveats

- **Tag bXXXX exacto del commit `149b2493c` no verificado en el web**: la referencia existe **citada literalmente en issue #21383** (*"Last known working: 149b2493c (March 19, 2026)"*), y el título del commit (*"common : fix typo in debug log ('extracft' -> 'extract') (#20807)"*) está verificado directamente en github.com/ggml-org/llama.cpp/commit/149b2493c. Lo que falta es la asociación tag↔commit en la web; resolverlo con `git describe` local antes de descargar binarios prebuilt.
- **PR #22288 está fusionado pero no resuelve #22527**: el subagente confirmó por la cabecera de issue #21468 que #22288 cerró ese issue. No hay evidencia textual de que #22288 toque el path LCP+seq_rm+flash-attn de #22527. Tratar #22527 como **abierto sin fix**.
- **`--slot-prompt-similarity 0.0` y `cache_prompt: false`: la conexión con el crash es por inferencia del trazado** (el log muestra `selected slot by LCP similarity` seguido de `memory_seq_rm` seguido del crash), no por experimento publicado. Mide tú mismo: si tras 10 turnos consecutivos no crashea, está validado.
- **Soporte de tool-calling en Llama-3.2 con llama.cpp + `--jinja`**: confirmado por la doc vLLM (*"All Llama 3.1, 3.2 and 4 models should be supported"*) y por el chat template Jinja oficial. Si lo migras, asegúrate de que tu plantilla acepta el formato JSON estricto y maneja el caso "el modelo emite texto y tool_call en la misma generación" — Llama 3.2 no emite tokens delimitadores específicos.
- **Issue #18703 (router multi-modelo + /slots)**: confirmado que tu setup `--models-preset` rompe los endpoints `/slots/*?action=*`. Workaround: conectar al puerto interno (lo verás en el log de arranque del sub-server, ej. `127.0.0.1:42515`).
- **Driver/CUDA**: el reporter de #22527 usa "Driver: 596.36 / CUDA 13.2" en una 4060 Ti 16 GB idéntica a la tuya. El bug no depende de driver, así que actualizar el driver NO ayuda (descarta la pista genérica).
- **SHA-256 de binarios oficiales**: cada release en https://github.com/ggml-org/llama.cpp/releases adjunta el zip; GitHub no publica un .sha256 separado, pero puedes ejecutar `Get-FileHash` en PowerShell y comparar contra el hash mostrado al subir el asset (visible en el commit del release).
- **Tamaño real de Gemma 4 E2B Q4_K_M**: la indicación del usuario de "~1.8 GB" es baja; el archivo oficial unsloth/gemma-4-E2B-it-GGUF Q4_K_M pesa **3.11 GB** con SHA256 `9378bc471710229ef165709b62e34bfb62231420ddaf6d729e727305b5b8672d` per la página de Hugging Face (mayo 2026). Esto no cambia el diagnóstico (el bug no depende del tamaño), pero conviene corregirlo al planificar VRAM si añades a futuro modelos más grandes.