# Investigación v2 — Bisect de builds llama-server entre b8607 y b8721 para Gemma 4 sin bug seq_rm

## Contexto nuevo (medido empíricamente esta sesión)

La investigación v1 (`PROMPT_RESEARCH_cuda_illegal_memory_gemma4.md`) recomendó
downgrade a commit `149b2493c` (19-mar-2026, ~b8580-b8606). Probamos con
**b8606** (1-abr-2026, último build de marzo según el changelog) y **el
binario NO soporta Gemma 4** — la arquitectura `gemma4.gguf` no se carga
porque fue añadida el 2-abr-2026 (lanzamiento del modelo).

Resumen empírico:
- **b9090** (build actual, 9-may-2026): tiene Gemma 4 ✅, tiene el bug seq_rm ❌
- **b8606** (1-abr-2026): NO tiene Gemma 4 ❌, no tiene el bug (no aplica)
- **b8607** (2-abr-2026): primer build con Gemma 4 (según fazm.ai blog)
- **b8721** (9-abr-2026): incluye PR #21418 (Gemma 4 specialized parser)

La regresión del bug está documentada en issue #21383 como introducida
entre `149b2493c` (19-mar) y `f49e91787` (3-abr). Hay una ventana muy
estrecha: **b8607 y b8608 (1-2 abr)** podrían tener Gemma 4 SIN la regresión.

## Prompt para Claude.ai

```
Necesito que investigues con precisión los builds de ggml-org/llama.cpp
entre b8607 y b8721 (release tags). Lo que necesito saber por cada build:

1. **¿Soporta la arquitectura Gemma 4 (gguf con metadata `general.architecture: gemma4`)?**
2. **¿Está incluido el PR #21418 ("common: add gemma 4 specialized parser",
   merged 4-abr-2026, "Included in build b8721")?** Sin este PR el tool
   calling de Gemma 4 produce respuestas corruptas.
3. **¿Está la regresión del bug seq_rm que dispara CUDA illegal memory
   access?** (issue #22527, #17109, #21383)

Específicamente para CADA uno de estos builds, dame el SHA del commit
HEAD del tag y la fecha de release:
- b8607
- b8608
- b8609
- b8610
- b8615
- b8620
- b8625
- b8630
- b8650
- b8680
- b8700
- b8720
- b8721

Si tienes acceso a los binarios Windows CUDA prebuilt para Windows x64
(`llama-bXXXX-bin-win-cuda-12.4-x64.zip` desde
https://github.com/ggml-org/llama.cpp/releases/tag/bXXXX), confirma que
existe el asset para cada uno.

## Lo que necesito saber

### Pregunta 1: ¿Existe un build con Gemma 4 + sin regresión?

El research anterior identificó que la regresión está entre `149b2493c`
(commit del 19-mar) y `f49e91787` (commit del 3-abr). Gemma 4 fue añadido
el 2-abr (build b8607+).

¿En la ventana b8607-b8610 (1-3 abr), ya hay Gemma 4 Y la regresión NO
ha entrado todavía? Investigá los commits específicos:
- ¿Qué commits del rango b8607-b8610 tocan `src/llama-memory-recurrent.cpp`,
  `src/llama-kv-cache.cpp`, `tools/server/server.cpp` (paths relacionados
  con seq_rm)?
- ¿Algún issue/discussion menciona usar b8607/b8608/b8609 con Gemma 4
  exitosamente?

### Pregunta 2: Si la regresión es anterior a b8607...

Entonces NO hay build con Gemma 4 sin el bug. En ese caso:

- ¿Existe un fork ACTIVO de llama.cpp que haya cherry-picked el fix de
  Gemma 4 (PR #21418, #21326, #21343) PERO mantenido el código de
  seq_rm de la era pre-regresión? (ik_llama.cpp tiene el bug heredado per
  issue #1693 confirmado).
- ¿Hay un commit master reciente (post mayo 2026) que arregla el bug
  seq_rm específicamente? Buscá PRs cerrados que mencionen "seq_rm",
  "memory_seq_rm", "MUL_MAT failed", "illegal memory access" + gemma.
- ¿Hay un release candidate o nightly de llama.cpp con un fix pendiente?

### Pregunta 3: Estrategia de bisecting si Pregunta 1 = NO

Si no hay build "limpio", investigá si vale la pena hacer git bisect
local entre los 93+ commits del rango `149b2493c..f49e91787`. Específicamente:

- Identifica los PRs del rango que tocan KV cache / SWA / memory ops:
  #19877 (mencionado en issue #21383), #19849, #19924, #20087, #20955.
  Cada uno: título, archivos cambiados, autor, fecha.
- ¿Cuál de estos PRs es el sospechoso primario de introducir el bug
  según los comentarios de issue #22527 y #21383?

### Pregunta 4: Soluciones alternativas finalmente confirmadas

Si todo lo anterior no da fix, **confirma cuál es la mejor entre estas**:

(A) Usar build b9090 actual + circuit breaker en cliente que limpia el
    slot cada 12 requests (ya implementado en mi código). Coste: cada
    12 turns hay ~50-100ms de erase + cache hit a 0% en el turn siguiente.

(B) Cambiar modelo a Llama-3.2-3B-Instruct-Q4_K_M (sin SWA). El research
    v1 lo mencionó. ¿Tiene tool calling robusto en español con prompts
    como los míos (system 23K chars, esquemas OpenAI)? Buscá benchmarks
    de tool-calling reliability en Llama 3.2 3B Q4 vs Gemma 4 E2B Q4.

(C) Cambiar modelo a Qwen2.5-3B-Instruct-Q4_K_M (sin SWA, mejor multilingüe).
    Mismo análisis: tool calling en español, configuración llama-server
    sin --swa-full.

(D) Compilar llama.cpp manualmente desde `f49e91787^` (parent del commit
    que introdujo el bug). Coste: setup de toolchain MSVC + CUDA Toolkit
    + compilar. ¿Hay docs específicas en `docs/build.md` para Windows
    CUDA 12.4 + RTX 4060 Ti (compute 8.9)?

## Formato esperado de la respuesta

Tabla concreta:

| Build | Date | Gemma4? | PR #21418? | Bug seq_rm? | Asset Win-CUDA12.4? |
|---|---|---|---|---|---|
| b8607 | 2-abr-2026 | sí/no | sí/no | sí/no | sí/no |
| b8608 | ... | ... | ... | ... | ... |

Si encuentras un build "sweet spot" (Gemma4 sí, bug no), dame el SHA-256
del asset Win-CUDA12.4 directo desde GitHub.

NO inventes datos. Si no se puede determinar empíricamente, dilo. Mejor
"no se sabe sin probar" que "probablemente b8610".
```

## Por qué este prompt v2 es más útil que el v1

- **Restringe la búsqueda** a una ventana de 15 builds en vez de "todos los anteriores"
- **Acepta** que `149b2493c` era pre-Gemma4 (corrige asunción del v1)
- **Pide datos tabulables** en vez de respuestas narrativas
- **Tiene un fallback claro** (Pregunta 4 con opciones medidas)
