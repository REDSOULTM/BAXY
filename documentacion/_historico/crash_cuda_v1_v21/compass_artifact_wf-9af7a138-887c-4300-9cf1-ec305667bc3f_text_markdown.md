# Investigación v2: ¿existe un build de llama.cpp (b8607–b8721) con Gemma 4 SIN la regresión de "illegal memory access" en seq_rm / prompt-cache?

## TL;DR
- **No se ha podido confirmar empíricamente ningún build con Gemma 4 libre del crash, y la evidencia apunta fuertemente a que NO existe**: el crash que sufres (issue #22527) está en el camino de código **SWA KV cache + context checkpoint** específico de Gemma 4, que llegó EXACTAMENTE con el soporte de Gemma 4 (b8607, PR #21309). No es una regresión introducida en una ventana posterior a b8607.
- **La premisa central de la v1 es incorrecta**: la "ventana de regresión `149b2493c..f49e91787`" pertenece al issue #21383, que es de **Qwen3.5-27B (modelo híbrido recurrente Mamba2/Gated Delta Net)**, un camino de código distinto. Además `f49e91787` NO es un commit que introduzca el bug: es literalmente el `master` HEAD del 3-abr-2026 cuando se reportó. Compilar desde `f49e91787^` no está justificado por la evidencia para tu crash de Gemma 4.
- **Mejor acción**: mantener b9090 + circuit breaker, pero PRIMERO probar `--ctx-checkpoints 0` (workaround documentado del path de checkpoints) y, si necesitas robustez de tool-calling sin SWA, migrar a **Qwen2.5-3B-Instruct-Q4_K_M**, que evita por completo el camino ISWA/checkpoint culpable.

## Key Findings

1. **Tu bug ≠ el bug de la v1.** El crash que reproduces (RTX 4060 Ti, Gemma 4, `--swa-full --flash-attn on`, tras `memory_seq_rm` post-LCP) corresponde al **issue #22527 — "Gemma 4 31B: illegal memory access after SWA KV cache checkpoint with Flash Attention enabled"** (abierto por `Xuan-GUo` el 29-abr-2026, build b8975-59237bfbb, RTX 4060 Ti 16 GB — exactamente tu hardware). El issue #21383 ("Qwen3.5-27B CUDA illegal memory access regression in prompt cache") es de arquitectura `qwen35` (híbrida atención + Mamba2/Gated Delta Net), distinta de Gemma 4. Son caminos de código distintos.

2. **`f49e91787` no es el commit culpable.** En #21383 se lee textualmente: *"First observed broken: f49e91787 (April 3, 2026, current master)"* y *"Not yet bisected to a single commit. Regression window: 149b2493c..f49e91787"*. Es decir, `f49e91787` es solo el HEAD de `master` el día del reporte, no un commit bisectado. El propio reportero no llegó a bisectar.

3. **El crash de Gemma 4 es intrínseco a su implementación SWA.** El issue #21690 indica que el bug de checkpoints en Gemma 4 es *"consistent since the initial implementation of Gemma 4"* y *"At least since b8660"*. Gemma 4 usa una arquitectura **ISWA de doble caché** (ratio 5:1 SWA:global, `head_dim` variable 256 SWA / 512 global, K=V en capas globales) introducida en el PR #21309 ("model: support gemma 4 (vision + moe, no audio)", de ngxson), que aterrizó en b8607. Por tanto, el camino de código que crashea **nació con el soporte de Gemma 4**. El propio #22527 documenta la raíz: con `--flash-attn off`, llama.cpp **rellena (padea) el V cache al tamaño máximo entre capas** (256 SWA vs 512 global), causando OOM; con flash-attn ON, crashea tras el segundo checkpoint SWA.

4. **Ni #22527 ni #21383 tienen PR de fix.** Ambos issues están ABIERTOS y, en su sección Development, muestran "No branches or pull requests" (verificado por fetch directo). No se encontró ningún PR mergeado en abril–mayo 2026 que afirme arreglar el crash de "SWA checkpoint / context checkpoint illegal memory access" para Gemma 4. #21383 está además etiquetado "stale".

5. **PR #21418** ("common: add gemma 4 specialized parser", de aldehir) está mergeado el **4-abr-2026** y arregla el tool-calling/parsing de Gemma 4 (añade `<|tool_response>` como EOG, emite JSON desde el AST de tool-call). Es **ortogonal al crash CUDA**: arregla salidas corruptas / loops infinitos de tool-calling, no la "illegal memory access".

## Details

### Verificación de existencia (fuentes primarias de GitHub)
- **#22527** verificado por fetch directo: título exacto, estado OPEN, abierto 29-abr-2026 por `Xuan-GUo`, **sin comentarios ni PRs vinculados**. Crash en `ggml-cuda.cu:3083`, `ggml_backend_cuda_synchronize`, `cudaStreamSynchronize(cuda_ctx->stream())`, tras el segundo "context checkpoint". El reportero probó: `--flash-attn off` (falla por VRAM por padding del V cache), reducir `-c`, `--cache-ram 0` (solo retrasa el crash ~2 turnos), `GGML_CUDA_GRAPHS=OFF` — todos fallan.
- **#21383** verificado por fetch directo: OPEN, etiquetado "stale", abierto 3-abr-2026 por `cutlerbenjamin1-cmd`, sin PRs vinculados. Menciona como sospechosos (sin bisectar) los PRs #20087, #19924, #19877, #19849, #20955 — todos del camino prompt-cache/checkpoint del modelo recurrente Qwen3.5, no del SWA de Gemma 4.
- **#17109** ("CUDA illegal memory access during K-Shift") y **#21140** (ROCm multi-GPU, recurrent state restore, device -1) existen y son reales, pero describen escenarios distintos.
- **ik_llama.cpp #1693** existe y es real: "Gemma-4 MoE IQ4_XS: NaN logits → sampling crash / CUDA illegal memory access after #1657" (abierto 25-abr-2026, RTX 4060 Laptop, `general.architecture str = gemma4`). Confirma que **el fork ik_llama.cpp también padece crashes con Gemma 4** (NaN logits → expert indices inválidos → illegal memory access), por lo que NO es una vía limpia.
- **PRs Gemma 4 verificados:** #21309 (soporte base), #21326 (template fixes), #21343 (tokenizer fix), #21390 (final_logit_softcapping), #21406 (custom newline split), #21418 (specialized parser, mergeado 4-abr-2026). Todos reales.

### Limitaciones de verificación (declaradas explícitamente)
No se pudieron abrir directamente las páginas de release/tag/tree ni de commits individuales por restricciones del fetch. Por tanto:
- **No se pudo confirmar el SHA exacto** del tag b8607 desde su página. Fuentes secundarias (fazm.ai) indican que b8607 (1-abr-2026) mergeó el PR #21038; el commit asociado a #21038 aparece como `744c0c7` ("llama : rotate activations for better quantization"), pero **el vínculo tag→SHA no está confirmado desde una página primaria de GitHub**. No lo tomes como verificado.
- **No se pudieron confirmar los mensajes/fechas reales** de los commits `149b2493c` y `f49e91787` desde sus páginas; solo se tiene la atribución del reportero de #21383 ("March 19" estable / "April 3" roto). `f49e917` sí aparece corroborado como commit real de llama.cpp en el changelog de llama-cpp-python (PR #2169), sin mensaje/fecha.
- **No se pudo ver la lista de assets de b8607.** El patrón `llama-bXXXX-bin-win-cuda-12.4-x64.zip` es el estándar del proyecto (confirmado en otros builds, p. ej. existe un mirror SourceForge de `llama-b8634-bin-win-cuda-12.4-x64.zip`), por lo que es altamente probable que `llama-b8607-bin-win-cuda-12.4-x64.zip` exista, pero no se ha visto la lista concreta del release b8607. **No hay "sweet spot" verificado, así que no procede aportar SHA-256 de ningún asset.**

### Tabla build-por-build
Leyenda de confianza: ✅ verificado en primaria; 🟡 inferido de fuente secundaria/patrón; ❓ no determinable sin probar.

| Build | Date | Gemma4? | PR #21418? | Bug seq_rm/SWA? | Asset Win-CUDA12.4? |
|---|---|---|---|---|---|
| b8607 | 1–2 abr 2026 🟡 | Sí 🟡 (primer build con Gemma 4, PR #21309) | No 🟡 (#21418 mergea 4-abr) | Probable Sí ❓ (path SWA nace aquí; #21690: "since initial impl") | Probable Sí 🟡 |
| b8608 | 2 abr 2026 🟡 | Sí 🟡 | No 🟡 | Probable Sí ❓ | Probable Sí 🟡 |
| b8609 | 2–3 abr 2026 🟡 | Sí 🟡 | No 🟡 | Probable Sí ❓ | Probable Sí 🟡 |
| b8610 | 3 abr 2026 🟡 | Sí 🟡 | No 🟡 | Probable Sí ❓ | Probable Sí 🟡 |
| b8615 | ~3 abr 2026 🟡 | Sí 🟡 | No 🟡 | Probable Sí ❓ | Probable Sí 🟡 |
| b8620 | ~3–4 abr 2026 🟡 | Sí 🟡 | No 🟡 | Probable Sí ❓ | Probable Sí 🟡 |
| b8625 | ~4 abr 2026 🟡 | Sí 🟡 | No/parcial 🟡 | Probable Sí ❓ | Probable Sí 🟡 |
| b8630 | ~4 abr 2026 🟡 | Sí 🟡 | ❓ | Probable Sí ❓ | Probable Sí 🟡 |
| b8650 | ~4 abr 2026 🟡 | Sí 🟡 | Probable Sí 🟡 (#21418 mergea 4-abr) | Probable Sí ❓ | Probable Sí 🟡 |
| b8680 | ~6 abr 2026 🟡 | Sí 🟡 | Sí 🟡 | Sí 🟡 (#21690: "al menos desde b8660") | Probable Sí 🟡 |
| b8700 | ~7–8 abr 2026 🟡 | Sí 🟡 | Sí 🟡 | Sí 🟡 | Probable Sí 🟡 |
| b8720 | ~9 abr 2026 🟡 | Sí 🟡 | Sí 🟡 | Sí 🟡 | Probable Sí 🟡 |
| b8721 | 9 abr 2026 🟡 | Sí 🟡 | Sí 🟡 (tarea: "Included in build b8721") | Sí 🟡 | Probable Sí 🟡 |

Nota: la tarea afirma que #21418 "Included in build b8721"; el blog fazm.ai sitúa el "Tool-call parser with JSON output and interleaved thinking" en b8665 (5-abr). El primer build que incluye #21418 está entre ~b8662 y b8721; no se puede fijar con exactitud sin las páginas de tag. **Ninguna fila puede marcarse "Bug = No" con confianza**: el path culpable existe desde b8607.

## Respuestas a las 4 preguntas

### QUESTION 1 — ¿Hay un build con Gemma 4 + SIN la regresión?
**Respuesta: Condicional, pero casi con certeza NO; "no se sabe con 100% sin probar" b8607–b8610.**
- **Evidencia**: el crash (#22527) está en el camino SWA KV cache + checkpoint propio de Gemma 4, introducido con el PR #21309 en b8607. El issue #21690 afirma que el bug de checkpoints es *"consistent since the initial implementation of Gemma 4"*. La "ventana `149b2493c..f49e91787`" es de #21383 (Qwen3.5), y **no acota tu bug**.
- **Sobre el "crux" planteado**: aunque la relación exacta tag↔commit no se pudo verificar en primaria, la dirección causal es clara: la regresión que importaba en la v1 (#21383) es de otro modelo/camino; tu crash de Gemma 4 no está delimitado por `f49e91787`. Como Gemma 4 y su path SWA-checkpoint **nacieron juntos en b8607**, no es esperable un build "Gemma4 sí, bug no".
- **Acción**: si quieres descartarlo empíricamente, prueba b8607/b8608 con `llama-b8607-bin-win-cuda-12.4-x64.zip` y tu config exacta (`--swa-full --flash-attn on --ctx-size 16384 --ngl 99 --parallel 1 --jinja`). Pero **NO** lo trates como solución de producción.
- **Coste**: una sesión de prueba (~30 min). **Caveat**: la evidencia hace improbable un resultado limpio.

### QUESTION 2 — Si la regresión precede a b8607...
**No aplica de la forma planteada**: no hay una regresión de `seq_rm` previa a Gemma 4 que sea TU bug; tu bug es intrínseco a la implementación SWA de Gemma 4. Sobre las alternativas pedidas:
- **Forks**: ik_llama.cpp **también crashea con Gemma 4** (issue #1693: NaN logits → illegal memory access en RTX 4060 Laptop). No es vía limpia. No se halló ningún fork mantenido (koboldcpp / croco / LostRuins) que haya cherry-pickeado el fix de Gemma 4 conservando un `seq_rm` "pre-regresión" y libre del crash.
- **Commit reciente que arregle el bug**: NO encontrado. Ni #22527 ni #21383 tienen PR de fix vinculado (ambos OPEN, "No branches or pull requests").
- **RC/nightly con fix pendiente**: no se halló evidencia.

### QUESTION 3 — Estrategia de bisect si Q1 = NO
**Poco recomendable para tu caso.** El rango `149b2493c..f49e91787` corresponde al bug de Qwen3.5 recurrente, no al SWA de Gemma 4; bisectar ahí no localizará tu crash. Los PRs citados como sospechosos en #21383 (#20087, #19924, #19877, #19849, #20955) son candidatos para el bug recurrente de Qwen3.5. Su verificación individual de título/autor/fecha no se pudo completar en primaria, así que no afirmo sus contenidos. Si insistes en bisectar, hazlo sobre el rango **b8607..b8975** (entre el nacimiento de Gemma 4 y el build donde #22527 se confirma), no sobre el rango de la v1.

### QUESTION 4 — Alternativas confirmadas
- **(A) b9090 + circuit breaker (cada 12 requests).** Funciona pero no elimina la causa. **Mejora concreta a probar primero**: añade `--ctx-checkpoints 0` (workaround del path de checkpoints según #21690) y/o `--cache-ram 0`. Coste: hit de cache 0% tras cada limpieza; la latencia de erase (~50–100 ms/ciclo) es tu propia medición interna, no externamente verificable. Es la opción de menor fricción si quieres seguir con Gemma 4.
- **(B) Llama-3.2-3B-Instruct-Q4_K_M (sin SWA).** Evita el path ISWA/checkpoint culpable. Tool-calling: Llama-3.2-3B-Instruct figura en BFCL en modo Prompt (no se pudo confirmar en primaria un valor overall exacto para 3.2-3B; como referencia verificada del paper BFCL, Llama-3.1-8B-Instruct (Prompt) = 39.6 overall). En español es funcional pero Qwen suele ser superior en multilingüe.
- **(C) Qwen2.5-3B-Instruct-Q4_K_M (sin SWA, mejor multilingüe). ← Recomendada.** Evita el path culpable; mejor opción para robustez + español. En el Berkeley Function Calling Leaderboard (BFCL), **Qwen2.5-3B-Instruct (FC) puntúa exactamente 38.7 overall** según el paper BFCL (Patil et al., 2025, OpenReview 2GmDdhBdDk: "Qwen2.5-3B-Instruct (FC) 38.7 · 73.3 [non-live]..."); en modo Prompt ≈ 35.7. Config sugerida: `llama-server -hf <repo> -ngl 99 -c 16384 --jinja -np 1 --flash-attn on` (**sin** `--swa-full`).
- **(D) Compilar desde `f49e91787^`.** **No recomendado**: la premisa es inválida para tu bug (f49e91787 no es el commit culpable de tu crash de Gemma 4). Si aun así compilas en Windows con RTX 4060 Ti (Ada Lovelace AD106, **CUDA Compute Capability 8.9** según la lista oficial de NVIDIA, developer.nvidia.com/cuda/gpus) + CUDA 12.4: `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="89"` y `cmake --build build --config Release`. docs/build.md confirma este patrón (lista RTX 4090 = 8.9 y el ejemplo `-DCMAKE_CUDA_ARCHITECTURES="86;89"`). Necesitarás MSVC + CUDA Toolkit instalados.

## Recommendations
1. **Inmediato (hoy)**: en b9090, probar `--ctx-checkpoints 0` (y opcionalmente `--cache-ram 0`) con tu config actual; medir si el crash desaparece. **Umbral de decisión**: si tras ~50 turnos agénticos no aparece "illegal memory access", quédate aquí.
2. **Si persiste**: migrar a **Qwen2.5-3B-Instruct-Q4_K_M** sin `--swa-full` (opción C). Es la vía más robusta porque elimina el camino ISWA/checkpoint culpable y aporta mejor multilingüe + BFCL FC 38.7. **Umbral**: si la fiabilidad de tool-calling en español es aceptable con tus prompts (~23K chars, schemas OpenAI), conviértelo en el default.
3. **NO** inviertas en bisect del rango `149b2493c..f49e91787` ni en compilar desde `f49e91787^` para este bug concreto; ambas acciones parten de una premisa que la evidencia contradice.
4. **Seguir** #22527 y #21383 para un eventual PR de fix; a día de hoy no existe ninguno vinculado.

## Caveats
- No se pudieron verificar en primaria: SHAs/fechas exactas de tags b8607–b8721, lista de assets por build, y mensajes/fechas reales de `149b2493c`/`f49e91787`. Los valores 🟡/❓ de la tabla reflejan esa incertidumbre. No hay "sweet spot" verificado, por lo que no se aporta SHA-256 de ningún asset (sería inventado).
- Las cifras BFCL son de modos "Prompt"/"FC" del paper/leaderboard; **no encontré entradas BFCL específicas para Gemma 4 E2B ni para Gemma-3 4B**, así que la comparación directa Gemma 4 vs Qwen/Llama en tool-calling es cualitativa, no medida punto-a-punto.
- "No se sabe sin probar" para b8607–b8610: la evidencia (PR #21309 introduce el path SWA en b8607; #21690 dice "since initial implementation") hace improbable un build limpio, pero no es una imposibilidad demostrada desde una página primaria de GitHub.
- Fechas exactas de builds intermedios (b8615–b8720) son aproximaciones a partir del rango abril-2026 documentado por fazm.ai; no se confirmaron tag a tag.